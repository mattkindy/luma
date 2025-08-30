"""Base types and definitions for tools."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.models.session import Session

ToolHandler = Callable[[BaseModel, Session], Awaitable[str]]
ToolCallable = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass
class ToolDefinition:
    """Definition of a tool available to the AI assistant."""

    name: str
    description: str
    input_schema_class: type[BaseModel]
    handler: ToolHandler

    def get_json_schema(self) -> dict[str, Any]:
        """Get JSON schema for this tool's input."""
        return self.input_schema_class.model_json_schema()

    def parse_input(self, raw_input: dict[str, Any]) -> BaseModel:
        """Parse and validate tool input."""
        return self.input_schema_class.model_validate(raw_input)
