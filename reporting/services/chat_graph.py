import asyncio
from functools import lru_cache
from typing import Annotated, Any, Protocol

import botocore.config
from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph_checkpoint_aws import DynamoDBSaver
from typing_extensions import TypedDict

from reporting import settings


class ChatState(TypedDict):
    messages: Annotated[list[Any], add_messages]


class ChatGraph(Protocol):
    def astream_events(
        self,
        input: ChatState,
        config: dict[str, Any],
        *,
        version: str,
        stream_mode: str,
    ) -> Any: ...


async def mock_agent_node(state: ChatState) -> ChatState:
    last_user_message = _last_user_text(state["messages"])
    response = f"I received your message: {last_user_message}"
    writer = get_stream_writer()

    for chunk in _chunk_text(response):
        writer({"kind": "token", "content": chunk})
        await asyncio.sleep(0.03)

    return {"messages": [AIMessage(content=response)]}


def _last_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _chunk_text(text: str, chunk_size: int = 8) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


@lru_cache(maxsize=1)
def get_chat_graph() -> ChatGraph:
    graph = StateGraph(ChatState)
    graph.add_node("mock_agent", mock_agent_node)
    graph.add_edge(START, "mock_agent")
    graph.add_edge("mock_agent", END)
    return graph.compile(checkpointer=_build_checkpointer())


def _build_checkpointer() -> DynamoDBSaver:
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
    return botocore.config.Config(
        connect_timeout=settings.AWS_CONNECT_TIMEOUT,
        read_timeout=settings.AWS_READ_TIMEOUT,
        s3={"addressing_style": "path"},
    )
