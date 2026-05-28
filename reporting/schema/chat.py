from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CHAT_THREAD_ID_PATTERN = r"^[0-9]+$"


class ChatStreamRequest(BaseModel):
    # Cap the message so a single turn can't store an unbounded payload in the
    # checkpoint (and, once a model is wired in, can't blow the token budget).
    message: str = Field(min_length=1, max_length=32000)
    thread_id: str = Field(min_length=1, max_length=32, pattern=CHAT_THREAD_ID_PATTERN)


class ChatHistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]


class ChatSessionItem(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSessionItem]


class CreateChatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=200)


class UpdateChatSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
