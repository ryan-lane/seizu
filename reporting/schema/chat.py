from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str = Field(min_length=1, max_length=200)
