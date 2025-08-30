"""Message and conversation data models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    """A message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    tool_calls: list[dict[str, Any]] | None = None


class ToolCall(BaseModel):
    """A tool call from the assistant."""

    id: str
    name: str
    input: dict[str, Any]


class ToolResult(BaseModel):
    """Result of a tool call."""

    tool_use_id: str
    content: str
    is_error: bool = False
