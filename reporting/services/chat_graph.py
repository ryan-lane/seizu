import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, Literal, Protocol

import botocore.config
from botocore.exceptions import ClientError
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph_checkpoint_aws import DynamoDBSaver
from mcp.types import Prompt, Tool
from typing_extensions import TypedDict

from reporting import settings
from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.services import mcp_runtime
from reporting.services.chat_messages import MessageTag, drop_tagged, has_tag, message_text, tag_message
from reporting.services.mcp_runtime import ChatBlockReason


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


class ChatModel(Protocol):
    def astream(
        self,
        input: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]: ...


@dataclass(frozen=True)
class ChatToolSpec:
    name: str
    kind: Literal["skill", "tool"]
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]
    spec: ChatToolSpec


@dataclass(frozen=True)
class ToolCallResult:
    request: ToolCallRequest
    content: str
    blocked: ChatBlockReason | None = None


class SeizuChatDeepSeekMixin:
    """Round-trip DeepSeek's OpenAI-API-shape ``reasoning_content`` field.

    DeepSeek emits its hidden chain-of-thought in the OpenAI Chat Completions
    streaming shape under ``choices[0].delta.reasoning_content``. The current
    ``langchain-deepseek`` adapter pulls that into ``AIMessageChunk.additional_kwargs``
    on the way down, but does not write it back into the assistant turn on the
    way up — so on a tool-call follow-up, DeepSeek loses its own thinking and
    quality regresses. This mixin patches both halves.

    Scope: DeepSeek only (and OpenAI-shape gateways routed to DeepSeek). It does
    not handle Anthropic ``ThinkingBlock`` or Gemini reasoning parts, which use
    different transport shapes; those providers don't need the round-trip
    today because their LangChain adapters already serialise thinking back.

    TODO: Remove this mixin when langchain-deepseek serialises
    ``reasoning_content`` back into assistant tool-call messages upstream.
    See https://github.com/langchain-ai/docs/issues/3765.
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict[str, Any],
        default_chunk_class: type,
        base_generation_info: dict[str, Any] | None,
    ) -> Any:
        generation_chunk = super()._convert_chunk_to_generation_chunk(  # type: ignore[misc]
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        reasoning_content = _deepseek_reasoning_content_delta(chunk)
        if reasoning_content and generation_chunk is not None and isinstance(generation_chunk.message, AIMessageChunk):
            generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning_content
        return generation_chunk

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        messages = self._convert_input(input_).to_messages()  # type: ignore[attr-defined]
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)  # type: ignore[misc]
        _add_reasoning_content_to_payload(payload, messages)
        return payload


_VALID_CHAT_PROVIDERS = frozenset({"mock", "openai", "anthropic", "gemini", "deepseek"})


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


async def mock_agent_node(state: ChatState, _config: RunnableConfig) -> ChatState:
    last_user_message = _last_user_text(state["messages"])
    response = f"I received your message: {last_user_message}"
    ai_message = AIMessage(content=response, id=f"msg_{uuid.uuid4().hex}")
    writer = get_stream_writer()

    # The mock has no real model behind it; emit small chunks with a sleep so
    # the dev SSE path still feels like a stream and exercises the same client
    # code as a real provider.
    for chunk in _chunk_text(response):
        writer({"kind": "token", "content": chunk})
        await asyncio.sleep(0.03)

    return {"messages": [*_trim_messages(state["messages"], ai_message), ai_message]}


async def chat_agent_node(state: ChatState, config: RunnableConfig) -> ChatState:
    provider = _chat_provider()
    if provider == "mock":
        return await mock_agent_node(state, config)

    current_user = _current_user_from_config(config)
    messages = _llm_context_messages(state["messages"])
    model = get_chat_model()
    writer = get_stream_writer()
    base_system_prompt = build_system_prompt(provider, current_user)

    # One listing per turn — every consumer below (capability context, skill
    # specs, tool specs) works off this snapshot. No cross-turn cache: each
    # turn sees the live store, and a single ``list_enabled_*`` call covers
    # every read the turn needs.
    skills = await _list_chat_prompts(current_user)
    tools: list[Tool] = []
    expose_tools = not settings.CHAT_LLM_PROGRESSIVE_DISCLOSURE
    if expose_tools:
        tools = await _list_chat_tools(current_user)

    capability_context = build_capability_context(skills, tools if expose_tools else None)
    if capability_context:
        base_system_prompt = f"{base_system_prompt}\n\n{capability_context}"

    skill_specs = _skill_tool_specs(skills)
    tool_specs: list[ChatToolSpec] = _mcp_tool_specs(tools) if expose_tools else []

    action_count = 0
    action_summaries: list[str] = []
    executed_action_keys: set[str] = set()
    empty_retry_used = False
    repeated_action_retry_used = False
    response_is_broken = False
    streamed_response = ""
    # Retry guidance for the *next* LLM call is appended to the system prompt
    # so it never appears as a mid-conversation SystemMessage (which several
    # provider adapters — most notably ChatAnthropic — discourage).
    pending_system_addendum = ""

    response = ""
    streamed_in_last_turn = ""
    while action_count < settings.CHAT_LLM_MAX_AUTO_ACTIONS:
        turn_system_prompt = _combined_system_prompt(base_system_prompt, pending_system_addendum)
        pending_system_addendum = ""
        available_specs = [*skill_specs, *tool_specs]
        ai_message, streamed_in_last_turn = await _run_llm_tool_turn(
            model,
            turn_system_prompt,
            messages,
            available_specs,
            config,
            writer,
        )
        streamed_response = streamed_in_last_turn
        unavailable = _unavailable_tool_call_results(ai_message, available_specs)
        if unavailable:
            action_summaries.append(_tool_call_user_summary(unavailable))
            response = _blocked_tool_call_response(unavailable)
            break

        requested = _tool_call_requests(ai_message, available_specs)
        if not requested:
            response = message_text(ai_message.content)
            if response:
                break
            if action_summaries:
                break
            if not empty_retry_used:
                empty_retry_used = True
                pending_system_addendum = _initial_empty_response_retry_message()
                continue
            break

        remaining = settings.CHAT_LLM_MAX_AUTO_ACTIONS - action_count
        batch = requested[:remaining]
        repeated = [request for request in batch if _tool_request_key(request) in executed_action_keys]
        batch = [request for request in batch if _tool_request_key(request) not in executed_action_keys]
        if not batch:
            if repeated:
                if not repeated_action_retry_used:
                    repeated_action_retry_used = True
                    messages = [*messages, ai_message]
                    pending_system_addendum = _repeated_tool_call_retry_message(repeated, action_summaries)
                    continue
                response = _repeated_tool_call_fallback(repeated, action_summaries)
                response_is_broken = True
                break
            break

        action_count += len(batch)
        executed_action_keys.update(_tool_request_key(request) for request in batch)
        writer({"kind": "token", "content": _tool_call_start_status(batch)})
        results = await _run_tool_call_batch(batch, current_user)
        action_summaries.append(_tool_call_user_summary(results))
        blocked_results = _blocked_tool_call_results(results)
        messages = [
            *messages,
            ai_message,
            *[
                ToolMessage(
                    content=result.content,
                    name=result.request.name,
                    tool_call_id=result.request.id,
                    id=f"msg_{uuid.uuid4().hex}",
                )
                for result in results
            ],
        ]
        messages = _trim_inner_loop_messages(messages, max_chars=settings.CHAT_LLM_CONTEXT_MAX_CHARS)
        if blocked_results:
            response = _blocked_tool_call_response(blocked_results)
            break
        if any(result.request.spec.kind == "skill" for result in results) and not expose_tools:
            expose_tools = True
            tools = await _list_chat_tools(current_user)
            tool_specs = _mcp_tool_specs(tools)

    if not response and action_summaries and not response_is_broken:
        synthesis_system_prompt = _combined_system_prompt(
            base_system_prompt, _final_synthesis_retry_message(action_summaries)
        )
        final_message, streamed_in_last_turn = await _run_llm_tool_turn(
            model, synthesis_system_prompt, messages, [], config, writer
        )
        streamed_response = streamed_in_last_turn
        response = message_text(final_message.content)

    if not response:
        response = _empty_response_fallback(action_summaries)
        response_is_broken = True

    # Streaming contract: the LLM-produced text is written to the writer as the
    # chunks arrive, so it is already on the wire. Synthetic fallbacks (and any
    # final tail not already streamed) are emitted here as a single delta.
    if response and response != streamed_response:
        if not streamed_response:
            writer({"kind": "token", "content": response})
        elif response.startswith(streamed_response):
            writer({"kind": "token", "content": response[len(streamed_response) :]})
        else:
            writer({"kind": "token", "content": f"\n\n{response}"})

    ai_message = AIMessage(content=response, id=f"msg_{uuid.uuid4().hex}")
    if response_is_broken:
        tag_message(ai_message, MessageTag.BROKEN)
    return {"messages": [*_trim_messages(state["messages"], ai_message), ai_message]}


def _combined_system_prompt(base: str, addendum: str) -> str:
    if not addendum:
        return base
    return f"{base}\n\n{addendum}"


async def _run_llm_tool_turn(
    model: ChatModel,
    system_prompt: str,
    messages: list[BaseMessage],
    tools: list[ChatToolSpec],
    config: RunnableConfig,
    writer: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[AIMessage, str]:
    """Run one LLM turn, streaming text deltas via *writer* as they arrive.

    Streaming policy: text deltas are emitted live *until* a chunk in this
    turn signals a tool call (tool_call_chunks, parsed tool_calls, or an
    Anthropic ``tool_use`` content block). After that, any remaining text in
    the turn is treated as pre-tool reasoning and is buffered into the merged
    message but not shown to the user — they would otherwise see "Let me
    check…" preambles that are about to be invalidated by a tool run.

    Returns ``(ai_message, streamed_text)``. ``streamed_text`` is the
    concatenation of deltas the caller has already shipped, so it can avoid
    re-emitting the final response if it matches.
    """
    runnable = model
    bind_tools = getattr(model, "bind_tools", None)
    if tools and callable(bind_tools):
        runnable = bind_tools([_langchain_tool_schema(tool) for tool in tools])

    merged: Any | None = None
    streamed = ""
    stream_text = writer is not None
    async for chunk in runnable.astream(
        [SystemMessage(content=system_prompt), *messages],
        config=config,
    ):
        if stream_text and _chunk_signals_tool_call(chunk):
            stream_text = False
        if stream_text and writer is not None:
            delta = message_text(getattr(chunk, "content", ""))
            if delta:
                writer({"kind": "token", "content": delta})
                streamed += delta
        merged = chunk if merged is None else merged + chunk

    if isinstance(merged, AIMessage):
        return merged, streamed
    fallback = AIMessage(
        content=message_text(getattr(merged, "content", "")) if merged is not None else "",
        tool_calls=list(getattr(merged, "tool_calls", []) or []),
        invalid_tool_calls=list(getattr(merged, "invalid_tool_calls", []) or []),
        id=getattr(merged, "id", None),
    )
    return fallback, streamed


def _chunk_signals_tool_call(chunk: Any) -> bool:
    """True if *chunk* carries a tool-call delta — partial or complete."""
    if getattr(chunk, "tool_call_chunks", None):
        return True
    if getattr(chunk, "tool_calls", None):
        return True
    if getattr(chunk, "invalid_tool_calls", None):
        return True
    # Anthropic streams ``tool_use`` blocks inside ``content`` as content-block
    # dicts; LangChain typically also surfaces them via ``tool_call_chunks`` but
    # we still check the content list so we trip on the earliest signal.
    content = getattr(chunk, "content", None)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") in ("tool_use", "tool_call"):
                return True
    return False


def _trim_inner_loop_messages(messages: list[BaseMessage], *, max_chars: int) -> list[BaseMessage]:
    """Cap the inner-turn message list by total character count.

    Tool results are bounded per call by ``CHAT_TOOL_RESULT_MAX_BYTES``, but
    nothing else stops the loop from accumulating up to
    ``CHAT_LLM_MAX_AUTO_ACTIONS`` × that cap into the next LLM call. This drops
    oldest AI+ToolMessage turn pairs from the head once the accumulated text
    exceeds the cap, keeping the user's original turn at index 0 (when it is a
    ``HumanMessage``) and the most recent tool exchange intact.
    """
    if max_chars <= 0 or len(messages) <= 4:
        return messages
    total = sum(_message_context_size(m) for m in messages)
    if total <= max_chars:
        return messages

    preserve_head = isinstance(messages[0], HumanMessage)
    head: list[BaseMessage] = [messages[0]] if preserve_head else []
    body = messages[1:] if preserve_head else messages[:]

    # Drop AIMessage + its trailing ToolMessages as a unit; orphaning tool
    # results breaks every provider's tool-call protocol.
    while body and total > max_chars:
        if not isinstance(body[0], AIMessage):
            dropped = body.pop(0)
            total -= _message_context_size(dropped)
            continue
        dropped = body.pop(0)
        total -= _message_context_size(dropped)
        while body and isinstance(body[0], ToolMessage):
            tool_dropped = body.pop(0)
            total -= _message_context_size(tool_dropped)

    return [*head, *body]


def _message_context_size(message: BaseMessage) -> int:
    size = len(message_text(getattr(message, "content", "")))
    if isinstance(message, AIMessage):
        reasoning_content = message.additional_kwargs.get("reasoning_content")
        if isinstance(reasoning_content, str):
            size += len(reasoning_content)
        if message.tool_calls:
            size += len(_json_dump(message.tool_calls))
        if message.invalid_tool_calls:
            size += len(_json_dump(message.invalid_tool_calls))
        raw_tool_calls = message.additional_kwargs.get("tool_calls")
        if raw_tool_calls:
            size += len(_json_dump(raw_tool_calls))
    if isinstance(message, ToolMessage):
        size += len(message.tool_call_id)
        if message.name:
            size += len(message.name)
    return size


def _langchain_tool_schema(tool: ChatToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or tool.name,
            "parameters": _json_schema_object(tool.input_schema),
        },
    }


def _json_schema_object(schema: dict[str, Any]) -> dict[str, Any]:
    result = dict(schema)
    result.setdefault("type", "object")
    result.setdefault("properties", {})
    return result


def _deepseek_reasoning_content_delta(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or []
    if not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if not isinstance(delta, dict):
        return ""
    reasoning_content = delta.get("reasoning_content")
    return reasoning_content if isinstance(reasoning_content, str) else ""


def _add_reasoning_content_to_payload(payload: dict[str, Any], messages: list[BaseMessage]) -> None:
    payload_messages = payload.get("messages")
    if not isinstance(payload_messages, list):
        return
    payload_index = 0
    for message in messages:
        if payload_index >= len(payload_messages):
            return
        payload_message = payload_messages[payload_index]
        payload_index += 1
        if not isinstance(message, AIMessage) or not isinstance(payload_message, dict):
            continue
        reasoning_content = message.additional_kwargs.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content:
            payload_message["reasoning_content"] = reasoning_content


def _uses_deepseek_compatible_endpoint(model_name: str) -> bool:
    base_url_host = _hostname(settings.CHAT_LLM_BASE_URL).lower()
    if base_url_host.endswith("deepseek.com") or base_url_host.endswith(".deepseek.com"):
        return True
    return model_name.lower().startswith("deepseek-")


def _hostname(url: str) -> str:
    if not url:
        return ""
    from urllib.parse import urlparse

    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _skill_tool_specs(skills: list[Prompt]) -> list[ChatToolSpec]:
    return [
        ChatToolSpec(
            name=prompt.name,
            kind="skill",
            description=prompt.description or f"{prompt.name} skill",
            input_schema=_prompt_input_schema(prompt),
        )
        for prompt in skills
    ]


def _mcp_tool_specs(tools: list[Tool]) -> list[ChatToolSpec]:
    return [
        ChatToolSpec(
            name=tool.name,
            kind="tool",
            description=tool.description or f"{tool.name} tool",
            input_schema=tool.inputSchema if isinstance(tool.inputSchema, dict) else {"type": "object"},
        )
        for tool in tools
    ]


async def _list_chat_tools(current_user: CurrentUser | None) -> list[Tool]:
    return await mcp_runtime.list_tools_for_user(
        current_user,
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
    )


async def _list_chat_prompts(current_user: CurrentUser | None) -> list[Prompt]:
    return await mcp_runtime.list_prompts_for_user(
        current_user,
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )


def _prompt_input_schema(prompt: Prompt) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for argument in prompt.arguments or []:
        properties[argument.name] = {
            "type": "string",
            "description": argument.description or argument.name,
        }
        if argument.required:
            required.append(argument.name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _tool_call_requests(message: AIMessage, specs: list[ChatToolSpec]) -> list[ToolCallRequest]:
    by_name = {spec.name: spec for spec in specs}
    requests: list[ToolCallRequest] = []
    for index, call in enumerate(getattr(message, "tool_calls", []) or []):
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
        if not isinstance(name, str) or name not in by_name:
            continue
        raw_args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
        args = raw_args if isinstance(raw_args, dict) else {}
        call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
        requests.append(
            ToolCallRequest(
                id=str(call_id or f"call_{index}_{uuid.uuid4().hex}"),
                name=name,
                arguments=args,
                spec=by_name[name],
            )
        )
    return requests


def _unavailable_tool_call_results(message: AIMessage, specs: list[ChatToolSpec]) -> list[ToolCallResult]:
    available_names = {spec.name for spec in specs}
    results: list[ToolCallResult] = []
    for index, call in enumerate(getattr(message, "tool_calls", []) or []):
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
        if not isinstance(name, str) or name in available_names:
            continue
        raw_args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
        args = raw_args if isinstance(raw_args, dict) else {}
        call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
        request = ToolCallRequest(
            id=str(call_id or f"call_{index}_{uuid.uuid4().hex}"),
            name=name,
            arguments=args,
            spec=ChatToolSpec(
                name=name,
                kind="tool",
                description="Unavailable in this chat context",
                input_schema={"type": "object"},
            ),
        )
        results.append(
            ToolCallResult(
                request=request,
                content=_json_dump({"error": f"Tool '{name}' is not available in this chat context"}),
                blocked=ChatBlockReason.NOT_AVAILABLE,
            )
        )
    return results


def _tool_request_key(request: ToolCallRequest) -> str:
    return f"{request.spec.kind}:{request.name}:{_json_dump(request.arguments)}"


async def _run_tool_call_batch(
    requests: list[ToolCallRequest], current_user: CurrentUser | None
) -> list[ToolCallResult]:
    max_parallel = settings.CHAT_LLM_MAX_PARALLEL_TOOL_CALLS
    semaphore = asyncio.Semaphore(max_parallel) if max_parallel > 0 else None

    async def run_one(request: ToolCallRequest) -> ToolCallResult:
        if semaphore is None:
            return await _run_tool_call(request, current_user)
        async with semaphore:
            return await _run_tool_call(request, current_user)

    return list(await asyncio.gather(*(run_one(request) for request in requests)))


async def _run_tool_call(request: ToolCallRequest, current_user: CurrentUser | None) -> ToolCallResult:
    if request.spec.kind == "skill":
        string_arguments = {key: str(value) for key, value in request.arguments.items()}
        outcome = await mcp_runtime.render_prompt_for_chat(
            current_user,
            request.name,
            string_arguments,
            gate_permission=Permission.CHAT_SKILLS_CALL,
        )
        return ToolCallResult(request=request, content=outcome.text, blocked=outcome.blocked)

    outcome = await mcp_runtime.call_tool_for_chat(
        current_user,
        request.name,
        request.arguments,
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
        result_max_rows=settings.CHAT_TOOL_RESULT_MAX_ROWS,
        result_max_bytes=settings.CHAT_TOOL_RESULT_MAX_BYTES,
    )
    return ToolCallResult(request=request, content=outcome.text, blocked=outcome.blocked)


def build_system_prompt(provider: str | None = None, current_user: CurrentUser | None = None) -> str:
    if settings.CHAT_LLM_SYSTEM_PROMPT:
        return settings.CHAT_LLM_SYSTEM_PROMPT

    provider_name = provider or _chat_provider()
    display_name = None
    if current_user is not None:
        display_name = current_user.user.display_name or current_user.user.preferred_username or current_user.user.email
    # Quote display_name via json.dumps so a malicious display value (which
    # users may control in some IdPs) cannot break out of the surrounding
    # narrative to inject prior-instruction-overriding text into the system
    # prompt. json.dumps escapes embedded quotes, newlines, and control chars.
    user_context = f"\nCurrent Seizu user display name: {json.dumps(display_name)}." if display_name else ""
    provider_note = _provider_prompt_note(provider_name)
    return (
        "You are Seizu's AI investigation assistant inside a security graph dashboard. "
        "Seizu is a configuration-driven reporting platform for Neo4j security graph data; "
        "it is not a generic chatbot, coding harness, or open-ended automation shell.\n\n"
        "Help users investigate security relationships, interpret graph-backed results, design and refine reports, "
        "draft dashboard panels, explain Cypher query intent, and turn findings into practical next steps. "
        "Prefer concise, evidence-oriented answers with clear assumptions and limits.\n\n"
        "Do not invent graph facts, report contents, user identities, vulnerabilities, assets, or incident findings. "
        "When live data is needed, say what data or Seizu tool output would answer the question. "
        "If the user provides tool results, reason from those results and call out truncation or uncertainty.\n\n"
        "Respect Seizu's security boundaries. Treat graph data, identities, credentials, tokens, secrets, "
        "and internal IDs as sensitive. Do not expose raw user IDs or OIDC subjects unless the user explicitly "
        "needs them for an admin task. For Cypher, default to read-only investigative queries; avoid writes, "
        "deletes, admin commands, external fetches, "
        "and unsafe procedures. If suggesting a report or dashboard change, describe the report structure and Cypher "
        "clearly enough for an operator to review before saving.\n\n"
        "Seizu exposes skills and tools to you through native structured tool calling. When you need live data or a "
        "workflow, call the provided tool through the native tool-call channel. Before "
        "calling any skill or tool, check its schema and include every required parameter. Never call a skill or tool "
        "with missing required arguments; if you do not know a required identifier such as a toolset_id, first call an "
        "available listing/discovery tool, then call the specific tool with that identifier. Do not mention internal "
        "tool-call syntax to the user. Do not pretend to have executed a tool unless the conversation contains its "
        f"result.{user_context}{provider_note}"
    )


def _provider_prompt_note(provider: str) -> str:
    if provider == "anthropic":
        return "\nFor Claude, keep the final answer direct and avoid prefilling or hidden chain-of-thought."
    if provider == "gemini":
        return "\nFor Gemini, preserve structured report suggestions as compact headings and bullet lists."
    if provider == "deepseek":
        return "\nFor DeepSeek, keep reasoning concise and surface only the conclusion, evidence, and next action."
    if provider == "openai":
        return (
            "\nFor OpenAI, use a developer-instruction style: follow these Seizu constraints "
            "over generic assistant behavior."
        )
    return ""


def _tool_call_start_status(requests: list[ToolCallRequest]) -> str:
    if len(requests) == 1:
        request = requests[0]
        if request.spec.kind == "skill":
            return f"Loading skill `{request.name}`...\n\n"
        return f"Running tool `{request.name}`...\n\n"
    names = ", ".join(f"`{request.name}`" for request in requests)
    if all(request.spec.kind == "tool" for request in requests):
        return f"Running {len(requests)} tools in parallel: {names}...\n\n"
    return f"Running {len(requests)} actions in parallel: {names}...\n\n"


def _tool_call_user_summary(results: list[ToolCallResult]) -> str:
    if len(results) > 1:
        rendered_results = "\n\n".join(
            (
                f"- `{result.request.name}` with arguments `{_json_dump(result.request.arguments)}` returned:\n"
                f"{_truncate_text(result.content, 1800)}"
            )
            for result in results
        )
        return f"Seizu ran {len(results)} actions in parallel:\n\n{rendered_results}"
    result = results[0]
    action = "rendered skill" if result.request.spec.kind == "skill" else "ran tool"
    return (
        f"Seizu {action} `{result.request.name}` with arguments `{_json_dump(result.request.arguments)}`.\n\n"
        f"Result:\n{_truncate_text(result.content, 4000)}"
    )


def _blocked_tool_call_results(results: list[ToolCallResult]) -> list[ToolCallResult]:
    return [result for result in results if result.blocked is not None]


def _blocked_tool_call_response(results: list[ToolCallResult]) -> str:
    lines = [
        "Seizu blocked the requested action because the tool or skill is not available to this chat session, "
        "or the current user/agent permissions do not allow it."
    ]
    for result in results:
        lines.append(
            f"- `{result.request.name}` with arguments `{_json_dump(result.request.arguments)}` was blocked "
            f"({_blocked_tool_call_reason_label(result.blocked)}): {_blocked_tool_call_body(result.content)}"
        )
    lines.append("No blocked action was executed.")
    return "\n".join(lines)


def _blocked_tool_call_reason_label(reason: ChatBlockReason | None) -> str:
    if reason == ChatBlockReason.PERMISSION_DENIED:
        return "permission denied"
    if reason == ChatBlockReason.NOT_AVAILABLE:
        return "not available in this chat session"
    return "blocked"


def _blocked_tool_call_body(content: str) -> str:
    """Extract the error message embedded in a chat-block result body, if any.

    Block results come from ``mcp_runtime`` with the explicit block reason on
    ``ToolCallResult.blocked``; this helper just picks the human-friendly
    error string out of the JSON body for user display. The decision to flag a
    result as blocked is *not* made here.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return content.strip() or "blocked"
    if isinstance(data, dict) and isinstance(data.get("error"), str):
        return data["error"]
    return content.strip() or "blocked"


def _repeated_tool_call_retry_message(requests: list[ToolCallRequest], action_summaries: list[str]) -> str:
    repeated = ", ".join(f"`{request.name}` with arguments `{_json_dump(request.arguments)}`" for request in requests)
    prior = (
        "\n\nMost recent completed action:\n" + _truncate_text(action_summaries[-1], 5000) if action_summaries else ""
    )
    return (
        "You requested an action Seizu has already run in this turn: "
        f"{repeated}. Do not repeat the same skill or tool call. Use the existing result to answer the user, or call "
        "a different tool only if it adds new required evidence. If you have enough evidence, provide the final "
        f"synthesis now.{prior}"
    )


def _repeated_tool_call_fallback(requests: list[ToolCallRequest], action_summaries: list[str]) -> str:
    repeated = ", ".join(f"`{request.name}`" for request in requests)
    details = (
        "\n\nMost recent completed action:\n" + _truncate_text(action_summaries[-1], 5000) if action_summaries else ""
    )
    return (
        "I stopped because the model repeatedly requested the same internal action instead of producing a final "
        f"answer. Repeated action: {repeated}.{details}"
    )


def _initial_empty_response_retry_message() -> str:
    return (
        "Your previous response was empty before Seizu could run any skill or tool. Retry now. Either answer the "
        "user directly, or use a structured skill/tool call with every required argument. Do not return an empty "
        "response."
    )


def _final_synthesis_retry_message(action_summaries: list[str]) -> str:
    joined_summaries = "\n".join(action_summaries)
    return (
        "Seizu has finished running the requested tool calls for this turn. Do not call any more tools. Provide the "
        "final answer to the user using the action results below. Summarize the evidence, note uncertainty or "
        f"truncation, and give practical next steps.\n\n{_truncate_text(joined_summaries, 12000)}"
    )


def _empty_response_fallback(action_summaries: list[str]) -> str:
    if not action_summaries:
        return (
            "The model returned an empty response after retrying, and Seizu did not run any skill or tool for this "
            "turn. Try rephrasing the request or starting a new chat thread."
        )
    return (
        "I ran the Seizu workflow, but the model did not return a final synthesis after the last action. "
        "The most recent action result is below, so the investigation state is not lost.\n\n"
        f"{_truncate_text(action_summaries[-1], 6000)}"
    )


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [truncated]"


def _json_dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def build_capability_context(skills: list[Prompt], tools: list[Tool] | None) -> str:
    """Build the capability section of the system prompt from already-listed data.

    The caller fetches the listings once per chat turn and threads them through
    here — keeps the hot path to a single store roundtrip per listing instead
    of re-listing once per consumer (capability context, skill specs, tool
    specs). Pass ``tools=None`` to render the progressive-disclosure variant
    (skills only).
    """
    if tools is None:
        return _progressive_capability_context(skills)
    return _full_capability_context(skills, tools)


def _progressive_capability_context(skills: list[Prompt]) -> str:
    if not skills:
        return ""
    return (
        "Capability discovery mode: progressive disclosure is enabled. You are initially given structured skill "
        "tools. When the task needs a workflow, call the relevant skill tool with every required argument. Seizu will "
        "execute it internally and return the rendered skill to you. Rendered skills describe which tools to use and "
        "how to use them; after a skill is rendered, Seizu will expose chat-safe structured tools for subsequent "
        "tool calls. Do not rely on tools that have not been disclosed by a rendered skill or by prior conversation "
        "context.\n\n"
        f"Available skills:\n{_format_skills(skills)}"
    )


def _full_capability_context(skills: list[Prompt], tools: list[Tool]) -> str:
    sections: list[str] = [
        "Capability discovery mode: progressive disclosure is disabled. You are given both chat-safe tools and "
        "skills up front, similar to a normal MCP listing. Use native structured tool calls and include every "
        "required argument shown for the selected skill or tool."
    ]
    if skills:
        sections.append(f"Available skills:\n{_format_skills(skills)}")
    if tools:
        sections.append(f"Available tools:\n{_format_tools(tools)}")
    return "\n\n".join(sections) if len(sections) > 1 else ""


def _format_skills(skills: list[Prompt]) -> str:
    lines: list[str] = []
    for skill in skills[:30]:
        args = _prompt_arguments(skill)
        description = skill.description or "No description"
        line = f"- {skill.name}: {description}"
        if args:
            line = f"{line} Args: {args}"
        lines.append(line)
    if len(skills) > 30:
        lines.append(f"- ...and {len(skills) - 30} more")
    return "\n".join(lines)


def _format_tools(tools: list[Tool]) -> str:
    lines: list[str] = []
    for tool in tools[:30]:
        description = tool.description or "No description"
        line = f"- {tool.name}: {description}"
        args = _tool_arguments(tool)
        if args:
            line = f"{line} Args: {args}"
        lines.append(line)
    if len(tools) > 30:
        lines.append(f"- ...and {len(tools) - 30} more")
    return "\n".join(lines)


def _prompt_arguments(prompt: Prompt) -> str:
    arguments = prompt.arguments or []
    if not arguments:
        return ""
    formatted: list[str] = []
    for argument in arguments:
        suffix = " required" if argument.required else " optional"
        formatted.append(f"{argument.name} ({suffix.strip()})")
    return ", ".join(formatted)


def _tool_arguments(tool: Tool) -> str:
    input_schema = tool.inputSchema
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if not isinstance(properties, dict):
        return ""
    required_raw = input_schema.get("required") if isinstance(input_schema, dict) else None
    required = set(required_raw) if isinstance(required_raw, list) else set()
    formatted = []
    for name in list(properties.keys())[:12]:
        suffix = " required" if name in required else " optional"
        formatted.append(f"{name} ({suffix.strip()})")
    if len(properties) > 12:
        formatted.append("...")
    return ", ".join(formatted)


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


def _llm_context_messages(messages: list[Any]) -> list[BaseMessage]:
    filtered = drop_tagged(messages, MessageTag.EPHEMERAL, MessageTag.BROKEN)
    context: list[BaseMessage] = []
    for message in filtered:
        if isinstance(message, HumanMessage):
            context.append(message)
        elif isinstance(message, AIMessage) and message_text(message.content) and not _is_broken_ai_message(message):
            context.append(message)

    max_messages = settings.CHAT_LLM_CONTEXT_MAX_MESSAGES
    if max_messages > 0:
        context = context[-max_messages:]

    max_chars = settings.CHAT_LLM_CONTEXT_MAX_CHARS
    if max_chars <= 0:
        return context

    retained: list[BaseMessage] = []
    total_chars = 0
    for message in reversed(context):
        text_len = len(message_text(message.content))
        if retained and total_chars + text_len > max_chars:
            break
        retained.append(message)
        total_chars += text_len
    return list(reversed(retained))


def _is_broken_ai_message(message: AIMessage) -> bool:
    if has_tag(message, MessageTag.BROKEN):
        return True
    text = message_text(message.content)
    normalized = " ".join(text.lower().split())
    return any(
        marker in normalized
        for marker in (
            "the model returned an empty response",
            "did not return a final synthesis",
            "did not run any skill or tool",
            "configured automatic action limit",
        )
    )


def _trim_messages(existing_messages: list[Any], new_message: AIMessage) -> list[RemoveMessage]:
    max_messages = settings.CHAT_MAX_PERSISTED_MESSAGES
    if max_messages <= 0:
        return []
    combined = [*existing_messages, new_message]
    remove_count = len(combined) - max_messages
    if remove_count <= 0:
        return []
    # Keep the retained window starting at a user turn: dropping an odd number
    # of messages can leave a leading assistant message orphaned from its
    # prompt, so shed it too. Never touches the just-produced message (the last
    # element), so we always retain at least the current turn.
    while remove_count < len(combined) - 1 and isinstance(combined[remove_count], AIMessage):
        remove_count += 1
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
    graph.add_node("chat_agent", chat_agent_node)
    graph.add_edge(START, "chat_agent")
    graph.add_edge("chat_agent", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_chat_graph() -> ChatGraph:
    return build_chat_graph(_build_checkpointer())


@lru_cache(maxsize=1)
def get_chat_model() -> ChatModel:
    provider = _chat_provider()
    if provider == "mock":
        raise RuntimeError("CHAT_LLM_PROVIDER=mock does not use a real chat model")
    model_name = _chat_model_name(provider)
    max_tokens = settings.CHAT_LLM_MAX_TOKENS if settings.CHAT_LLM_MAX_TOKENS > 0 else None

    if provider == "openai":
        kwargs = _chat_model_kwargs(settings.OPENAI_API_KEY, include_base_url=True)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        cls = _openai_chat_class(deepseek_compatible=_uses_deepseek_compatible_endpoint(model_name))
        return cls(model=model_name, **kwargs)

    if provider == "deepseek":
        kwargs = _chat_model_kwargs(settings.DEEPSEEK_API_KEY, include_base_url=True)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return _deepseek_chat_class()(model=model_name, **kwargs)

    if provider == "anthropic":
        kwargs = _chat_model_kwargs(settings.ANTHROPIC_API_KEY, include_base_url=True)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name, **kwargs)

    # gemini — ChatGoogleGenerativeAI does not accept a base_url kwarg, so the
    # operator-set CHAT_LLM_BASE_URL is intentionally not forwarded here.
    kwargs = _chat_model_kwargs(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY, include_base_url=False)
    if max_tokens is not None:
        kwargs["max_output_tokens"] = max_tokens
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model_name, **kwargs)


@lru_cache(maxsize=2)
def _openai_chat_class(deepseek_compatible: bool) -> type:
    from langchain_openai import ChatOpenAI

    if not deepseek_compatible:
        return ChatOpenAI

    class SeizuChatOpenAI(SeizuChatDeepSeekMixin, ChatOpenAI):
        pass

    return SeizuChatOpenAI


@lru_cache(maxsize=1)
def _deepseek_chat_class() -> type:
    from langchain_deepseek import ChatDeepSeek

    class SeizuChatDeepSeek(SeizuChatDeepSeekMixin, ChatDeepSeek):
        pass

    return SeizuChatDeepSeek


def _chat_provider() -> str:
    provider = settings.CHAT_LLM_PROVIDER.strip().lower()
    if provider not in _VALID_CHAT_PROVIDERS:
        raise ValueError("CHAT_LLM_PROVIDER must be one of: " + ", ".join(sorted(_VALID_CHAT_PROVIDERS)))
    return provider


def _chat_model_name(provider: str) -> str:
    model = settings.CHAT_LLM_MODEL.strip()
    if not model:
        raise ValueError(
            f"CHAT_LLM_MODEL is required when CHAT_LLM_PROVIDER={provider!r}. Set it to a model identifier "
            "supported by the provider (e.g. an OpenAI/Anthropic/Gemini/DeepSeek model name). The mock provider "
            "is the only one that runs without a model."
        )
    return model


def _chat_model_kwargs(provider_api_key: str, *, include_base_url: bool) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "temperature": settings.CHAT_LLM_TEMPERATURE,
        "timeout": settings.CHAT_LLM_TIMEOUT_SECONDS,
        "max_retries": settings.CHAT_LLM_MAX_RETRIES,
    }
    api_key = settings.CHAT_LLM_API_KEY or provider_api_key
    if api_key:
        kwargs["api_key"] = api_key
    if include_base_url and settings.CHAT_LLM_BASE_URL:
        kwargs["base_url"] = settings.CHAT_LLM_BASE_URL
    return kwargs


def validate_chat_llm_config() -> None:
    """Fail-fast validation called at startup when chat is enabled.

    Raises ``ValueError`` if ``CHAT_LLM_PROVIDER`` is unknown or, for a real
    provider, ``CHAT_LLM_MODEL`` is missing. Catches typos that previously
    surfaced only on the first user request.
    """
    provider = _chat_provider()
    if provider == "mock":
        return
    _chat_model_name(provider)


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
