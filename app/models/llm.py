"""LLM-related data models and types (provider-agnostic)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel


# Content block types
class TextBlock(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str

    class Config:
        extra = "ignore"  # Ignore any additional fields from Anthropic


class ToolUseBlock(BaseModel):
    """Tool use content block."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]

    class Config:
        extra = "ignore"  # Ignore any additional fields from Anthropic


class ToolResultBlock(BaseModel):
    """Tool result content block."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False

    class Config:
        extra = "ignore"  # Ignore any additional fields from Anthropic


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


class LLMMessage(BaseModel):
    """A message for LLM conversation."""

    role: Literal["user", "assistant", "system"]
    content: str | list[ContentBlock]


class LLMToolSchema(BaseModel):
    """Schema definition for an LLM tool."""

    description: str
    input_schema: dict[str, Any]


@dataclass
class LLMTool:
    """Tool with both schema and callable."""

    name: str
    description: str
    input_schema: dict[str, Any]
    callable: Callable[[dict[str, Any]], Awaitable[str]]


class LLMToolDefinition(BaseModel):
    """Complete tool definition for LLM."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class LLMUsage:
    """Token/resource usage information from LLM provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total_input = self.input_tokens + self.cache_read_input_tokens + self.cache_creation_input_tokens
        if total_input == 0:
            return 0.0
        return (self.cache_read_input_tokens / total_input) * 100

    @property
    def cost_savings_percentage(self) -> float:
        """Calculate cost savings from caching as percentage of total cost."""
        total_input_tokens = self.input_tokens + self.cache_read_input_tokens + self.cache_creation_input_tokens
        if total_input_tokens == 0:
            return 0.0

        normal_cost = total_input_tokens * 1.0  # Base rate

        actual_cost = (
            self.input_tokens * 1.0  # Regular input tokens
            + self.cache_creation_input_tokens * 1.25  # Cache writes (25% more)
            + self.cache_read_input_tokens * 0.1  # Cache reads (10% of base)
        )

        savings = normal_cost - actual_cost
        return (savings / normal_cost) * 100 if normal_cost > 0 else 0.0


@dataclass
class LLMResponse:
    """Provider-agnostic response from LLM service."""

    content: list[ContentBlock]
    stop_reason: str | None
    usage: LLMUsage | None
    model: str
    provider: str = "anthropic"


@dataclass
class AgentLoopResult:
    """Result from executing an agent loop."""

    content: list[ContentBlock]
    stop_reason: str | None
    messages: list[LLMMessage]
    turns: int
    usage: LLMUsage | None
