import asyncio
import uuid
from functools import lru_cache
from typing import Annotated, Any, Protocol

import botocore.config
from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph_checkpoint_aws import DynamoDBSaver
from typing_extensions import TypedDict

from reporting import settings
from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.services import mcp_runtime
from reporting.services.chat_commands import SlashCommand, SlashCommandError, parse_slash_command
from reporting.services.chat_messages import MessageTag, drop_tagged, tag_message


class ChatState(TypedDict):
    messages: Annotated[list[Any], add_messages]


class ChatGraph(Protocol):
    def astream(
        self,
        input: ChatState,
        config: dict[str, Any],
        *,
        stream_mode: str,
    ) -> Any: ...

    def aget_state(self, config: dict[str, Any]) -> Any: ...


def namespaced_thread_id(current_user: CurrentUser, thread_id: str) -> str:
    """Scope a client-supplied thread id to the authenticated user.

    The user id prefix is server-derived, so a client cannot reach another
    user's thread by guessing the thread id.
    """
    return f"user:{current_user.user.user_id}:thread:{thread_id}"


async def load_thread_messages(current_user: CurrentUser, thread_id: str, *, limit: int) -> list[Any]:
    """Return the persisted LangChain messages for a user's chat thread.

    Ephemeral-tagged messages are filtered out here so they never reach the
    history API or (in future) the LLM context, even if some code path persists
    one — the tag is the single enforcement point.
    """
    graph = get_chat_graph()
    config = {"configurable": {"thread_id": namespaced_thread_id(current_user, thread_id)}}
    state = await graph.aget_state(config)
    values = getattr(state, "values", None) or {}
    messages = values.get("messages", [])
    if not isinstance(messages, list):
        return []
    filtered = drop_tagged(messages, MessageTag.EPHEMERAL)
    return filtered[-limit:] if limit > 0 else []


def is_ephemeral_command(text: str) -> bool:
    """True for console commands handled out-of-band (streamed, not persisted)."""
    try:
        return parse_slash_command(text) is not None
    except SlashCommandError:
        command = text.strip().split(maxsplit=1)[0]
        return command in {"/tools", "/tool", "/skills", "/skill"}


def classify_input(text: str) -> HumanMessage:
    """Build the user message for a turn, tagging it ephemeral when it is a
    console command whose turn should be streamed but never persisted."""
    message = HumanMessage(content=text, id=f"msg_{uuid.uuid4().hex}")
    if is_ephemeral_command(text):
        tag_message(message, MessageTag.EPHEMERAL)
    return message


async def mock_agent_node(state: ChatState, config: RunnableConfig) -> ChatState:
    last_user_message = _last_user_text(state["messages"])
    current_user = _current_user_from_config(config)
    response = await build_agent_response(last_user_message, current_user)
    ai_message = AIMessage(content=response, id=f"msg_{uuid.uuid4().hex}")
    writer = get_stream_writer()

    for chunk in _chunk_text(response):
        writer({"kind": "token", "content": chunk})
        await asyncio.sleep(0.03)

    return {"messages": [*_trim_messages(state["messages"], ai_message), ai_message]}


async def build_agent_response(message: str, current_user: CurrentUser | None) -> str:
    try:
        command = parse_slash_command(message)
    except SlashCommandError as exc:
        return str(exc)
    if command is None:
        return f"I received your message: {message}"
    if command.command == "tools":
        return await _list_tools_response(current_user)
    if command.command == "tool":
        return await _call_tool_response(command, current_user)
    if command.command == "skills":
        return await _list_skills_response(current_user)
    if command.command == "skill":
        return await _render_skill_response(command, current_user)
    return f"I received your message: {message}"


async def _list_tools_response(current_user: CurrentUser | None) -> str:
    tools = await mcp_runtime.list_tools_for_user(
        current_user,
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
    )
    if not tools:
        return "No MCP tools are available to this chat session."
    lines = [f"- {tool.name}: {tool.description or 'No description'}" for tool in tools[:30]]
    if len(tools) > 30:
        lines.append(f"- ...and {len(tools) - 30} more")
    return "Available MCP tools:\n" + "\n".join(lines)


async def _call_tool_response(command: SlashCommand, current_user: CurrentUser | None) -> str:
    if not command.name:
        return "Expected `/tool <name> {...json args...}`."
    result = await mcp_runtime.call_tool_for_user(
        current_user,
        command.name,
        command.arguments,
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
        result_max_rows=settings.CHAT_TOOL_RESULT_MAX_ROWS,
        result_max_bytes=settings.CHAT_TOOL_RESULT_MAX_BYTES,
    )
    return _text_content_response(result)


async def _list_skills_response(current_user: CurrentUser | None) -> str:
    prompts = await mcp_runtime.list_prompts_for_user(
        current_user,
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )
    if not prompts:
        return "No MCP skills are available to this chat session."
    lines = [f"- {prompt.name}: {prompt.description or 'No description'}" for prompt in prompts[:30]]
    if len(prompts) > 30:
        lines.append(f"- ...and {len(prompts) - 30} more")
    return "Available MCP skills:\n" + "\n".join(lines)


async def _render_skill_response(command: SlashCommand, current_user: CurrentUser | None) -> str:
    if not command.name:
        return "Expected `/skill <name> {...json args...}`."
    string_arguments = {key: str(value) for key, value in command.arguments.items()}
    result = await mcp_runtime.get_prompt_for_user(
        current_user,
        command.name,
        string_arguments,
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )
    return "\n\n".join(text for message in result.messages if (text := _content_text(message.content)))


def _text_content_response(content: list[Any]) -> str:
    return "\n\n".join(item.text for item in content if hasattr(item, "text"))


def _content_text(content: Any) -> str | None:
    text = getattr(content, "text", None)
    return text if isinstance(text, str) else None


def _current_user_from_config(config: RunnableConfig) -> CurrentUser | None:
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    current_user = configurable.get("current_user")
    return current_user if isinstance(current_user, CurrentUser) else None


def _last_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _trim_messages(existing_messages: list[Any], new_message: AIMessage) -> list[RemoveMessage]:
    max_messages = settings.CHAT_MAX_PERSISTED_MESSAGES
    if max_messages <= 0:
        return []
    combined = [*existing_messages, new_message]
    remove_count = len(combined) - max_messages
    if remove_count <= 0:
        return []
    removals: list[RemoveMessage] = []
    for message in combined[:remove_count]:
        message_id = getattr(message, "id", None)
        if isinstance(message_id, str) and message_id:
            removals.append(RemoveMessage(id=message_id))
    return removals


def _chunk_text(text: str, chunk_size: int = 8) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def build_chat_graph(checkpointer: Any) -> ChatGraph:
    graph = StateGraph(ChatState)
    graph.add_node("mock_agent", mock_agent_node)
    graph.add_edge(START, "mock_agent")
    graph.add_edge("mock_agent", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_chat_graph() -> ChatGraph:
    return build_chat_graph(_build_checkpointer())


def _build_checkpointer() -> DynamoDBSaver:
    # DynamoDBSaver is boto3-based (no async DynamoDB saver ships in
    # langgraph-checkpoint-aws), but its async methods wrap the sync calls in
    # run_in_executor, so checkpoint I/O is offloaded to a threadpool and does
    # not block the event loop — keep using it under the async graph.
    ttl_seconds = settings.CHAT_CHECKPOINT_TTL_SECONDS or None
    s3_offload_config = None
    if settings.CHAT_CHECKPOINT_S3_BUCKET:
        s3_offload_config = {
            "bucket_name": settings.CHAT_CHECKPOINT_S3_BUCKET,
            "endpoint_url": settings.CHAT_CHECKPOINT_S3_ENDPOINT_URL or None,
            "key_prefix": settings.CHAT_CHECKPOINT_S3_KEY_PREFIX or None,
        }
    return DynamoDBSaver(
        table_name=settings.CHAT_CHECKPOINT_TABLE_NAME,
        region_name=settings.DYNAMODB_REGION,
        endpoint_url=settings.DYNAMODB_ENDPOINT_URL or None,
        boto_config=_aws_config(),
        ttl_seconds=ttl_seconds,
        enable_checkpoint_compression=settings.CHAT_CHECKPOINT_ENABLE_COMPRESSION,
        s3_offload_config=s3_offload_config,
    )


async def initialize_chat_checkpoints() -> None:
    if settings.CHAT_CHECKPOINT_CREATE_TABLE:
        await asyncio.to_thread(_initialize_chat_checkpoints_sync)


def _initialize_chat_checkpoints_sync() -> None:
    checkpointer = _build_checkpointer()
    client = checkpointer.client
    table_name = settings.CHAT_CHECKPOINT_TABLE_NAME

    try:
        client.describe_table(TableName=table_name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        try:
            client.create_table(
                TableName=table_name,
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                ],
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
        except ClientError as create_exc:
            if create_exc.response["Error"]["Code"] != "ResourceInUseException":
                raise
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)

    if settings.CHAT_CHECKPOINT_TTL_SECONDS:
        try:
            client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
            )
        except ClientError as ttl_exc:
            error = ttl_exc.response["Error"]
            message = error.get("Message", "")
            if error["Code"] != "ValidationException" or (
                "already enabled" not in message and "being enabled" not in message
            ):
                raise


def _aws_config() -> botocore.config.Config:
    config_kwargs: dict[str, Any] = {
        "connect_timeout": settings.AWS_CONNECT_TIMEOUT,
        "read_timeout": settings.AWS_READ_TIMEOUT,
    }
    # Path-style addressing is required for S3-compatible endpoints like MinIO
    # in development; against real AWS S3 leave the default (virtual-hosted),
    # which is the recommended/forward-compatible style.
    if settings.CHAT_CHECKPOINT_S3_ENDPOINT_URL:
        config_kwargs["s3"] = {"addressing_style": "path"}
    return botocore.config.Config(**config_kwargs)
