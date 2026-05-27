from typing import Literal

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    # Cap the message so a single turn can't store an unbounded payload in the
    # checkpoint (and, once a model is wired in, can't blow the token budget).
    message: str = Field(min_length=1, max_length=32000)
    thread_id: str = Field(min_length=1, max_length=200)


class ChatHistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
