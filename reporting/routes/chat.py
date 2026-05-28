import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from reporting import settings
from reporting.authnz import CurrentUser, require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.chat import ChatHistoryMessage, ChatHistoryResponse, ChatStreamRequest
from reporting.services.chat_graph import (
    ChatState,
    get_chat_graph,
    load_thread_messages,
    namespaced_thread_id,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/api/v1/chat/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-sent event stream",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def stream_chat(
    body: ChatStreamRequest,
    current: CurrentUser = Depends(require_permission(Permission.CHAT_USE)),
) -> StreamingResponse:
    """Stream a chat response as an AI SDK UI Message Stream."""
    return StreamingResponse(
        _stream_chat_response(body, current),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


async def _stream_chat_response(body: ChatStreamRequest, current: CurrentUser) -> AsyncIterator[str]:
    message_id = f"msg_{uuid.uuid4().hex}"
    text_id = f"text_{uuid.uuid4().hex}"

    yield _sse_data({"type": "start", "messageId": message_id})
    yield _sse_data({"type": "text-start", "id": text_id})

    try:
        async for delta in _token_source(body, current):
            if delta:
                yield _sse_data({"type": "text-delta", "id": text_id, "delta": delta})
    except Exception:
        logger.exception("Chat stream failed")
        yield _sse_data({"type": "text-end", "id": text_id})
        yield _sse_data({"type": "error", "errorText": "Chat stream failed"})
        yield _sse_data({"type": "finish", "finishReason": "error"})
        yield "data: [DONE]\n\n"
        return

    yield _sse_data({"type": "text-end", "id": text_id})
    yield _sse_data({"type": "finish", "finishReason": "stop"})
    yield "data: [DONE]\n\n"


async def _token_source(body: ChatStreamRequest, current: CurrentUser) -> AsyncIterator[str]:
    graph = get_chat_graph()
    graph_input: ChatState = {"messages": [HumanMessage(content=body.message, id=f"msg_{uuid.uuid4().hex}")]}
    config = {
        "configurable": {
            "current_user": current,
            "thread_id": namespaced_thread_id(current, body.thread_id),
        }
    }
    async for chunk in graph.astream(graph_input, config, stream_mode="custom"):
        if isinstance(chunk, dict) and chunk.get("kind") == "token":
            delta = chunk.get("content")
            if isinstance(delta, str):
                yield delta


def _sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


@router.get("/api/v1/chat/history", response_model=ChatHistoryResponse)
async def chat_history(
    thread_id: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=settings.CHAT_HISTORY_LIMIT, ge=1, le=500),
    current: CurrentUser = Depends(require_permission(Permission.CHAT_USE)),
) -> ChatHistoryResponse:
    """Return the persisted messages for the caller's chat thread.

    Lets the SPA rehydrate a conversation after a reload, since the client-side
    message state is otherwise lost.
    """
    messages = await load_thread_messages(current, thread_id, limit=limit)
    return ChatHistoryResponse(
        messages=[message for index, item in enumerate(messages) if (message := _to_history_message(item, index))]
    )


def _to_history_message(message: Any, index: int) -> ChatHistoryMessage | None:
    if isinstance(message, HumanMessage):
        role: str = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        # Skip system/tool messages — the UI only renders the user/assistant turns.
        return None
    text = _message_text(message.content)
    if not text:
        return None
    message_id = str(message.id) if message.id else f"{role}-{index}"
    return ChatHistoryMessage(id=message_id, role=role, text=text)


def _message_text(content: Any) -> str:
    """Flatten LangChain message content (str or content blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""
