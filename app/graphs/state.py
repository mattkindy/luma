"""State definitions for LangGraph conversation flow."""

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


class PatientInfo(BaseModel):
    """Patient verification and session state."""

    patient_id: str | None = None
    verified: bool = False
    failed_attempts: int = 0


class ToolCall(BaseModel):
    """Represents a tool call request."""

    id: str
    name: str
    args: dict[str, Any]


class ToolResult(BaseModel):
    """Result from tool execution."""

    tool_call_id: str
    content: str
    is_error: bool = False


class ConversationState(BaseModel):
    """Main conversation state for LangGraph.

    This state is passed through all nodes in the graph and maintains
    the complete conversation context.
    """

    # Core conversation data
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str

    # Patient verification state
    patient_info: PatientInfo

    # Tool execution tracking
    pending_tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)

    # Control flow
    next_step: Literal["agent", "tools", "verify", "error", "end"] | None = None
    error: str | None = None
    retry_count: int = 0

    # Token usage tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True  # Allow BaseMessage types
