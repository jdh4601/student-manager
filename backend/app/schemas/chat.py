from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    thread_id: UUID | None = None
    message: str = Field(min_length=1, max_length=1000)


class StudentRef(BaseModel):
    id: UUID
    name: str


class ChatResponse(BaseModel):
    thread_id: UUID
    reply: str
    referenced_students: list[StudentRef] = Field(default_factory=list)
