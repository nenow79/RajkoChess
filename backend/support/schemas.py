import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TicketCategory = Literal["problem", "idea", "question"]
TicketStatus = Literal["open", "waiting_user", "closed"]


def _normalized(value: str) -> str:
    return value.strip()


class TicketCreate(BaseModel):
    category: TicketCategory
    subject: str = Field(min_length=5, max_length=160)
    message: str = Field(min_length=3, max_length=5000)

    @field_validator("subject", "message", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return _normalized(value) if isinstance(value, str) else value


class TicketMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=5000)

    @field_validator("message", mode="before")
    @classmethod
    def normalize_message(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = _normalized(value)
        if not normalized:
            raise ValueError("Wiadomość nie może być pusta")
        return normalized


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class TicketRead(BaseModel):
    through_message_id: uuid.UUID
