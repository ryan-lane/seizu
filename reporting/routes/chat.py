import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from reporting.authnz import CurrentUser, require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.chat import ChatStreamRequest
from reporting.services.chat_graph import ChatState, get_chat_graph

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
        graph = get_chat_graph()
        graph_input: ChatState = {"messages": [HumanMessage(content=body.message)]}
        config = {
            "configurable": {
                "current_user": current,
                "thread_id": f"user:{current.user.user_id}:thread:{body.thread_id}",
            }
        }
        async for event in graph.astream_events(
            graph_input,
            config,
            version="v2",
            stream_mode="custom",
        ):
            token = _token_from_event(event)
            if token:
                yield _sse_data({"type": "text-delta", "id": text_id, "delta": token})
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


def _token_from_event(event: dict[str, Any]) -> str | None:
    if event.get("event") != "on_chain_stream":
        return None
    if event.get("parent_ids"):
        return None
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    chunk = data.get("chunk")
    if not isinstance(chunk, dict):
        return None
    if chunk.get("kind") != "token":
        return None
    content = chunk.get("content")
    return content if isinstance(content, str) else None


def _sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
