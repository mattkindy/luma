"""Tools registry for managing AI assistant tools."""

from typing import Any

from app.models.llm import LLMTool
from app.models.session import Session
from app.services.appointments import AppointmentService
from app.services.verification import PatientVerificationService
from app.tools.appointment_actions import create_cancel_appointment_tool, create_confirm_appointment_tool
from app.tools.base import ToolCallable, ToolDefinition
from app.tools.list_appointments import create_list_appointments_tool
from app.tools.verify_patient import create_verify_patient_tool


class ToolsRegistry:
    """Registry for managing AI assistant tools."""

    def __init__(self, verification_service: PatientVerificationService, appointment_service: AppointmentService):
        """Initialize tools registry with service dependencies."""
        self.verification_service = verification_service
        self.appointment_service = appointment_service
        self._tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools for healthcare appointment management."""
        tools = [
            create_verify_patient_tool(self.verification_service),
            create_list_appointments_tool(self.appointment_service),
            create_confirm_appointment_tool(self.appointment_service),
            create_cancel_appointment_tool(self.appointment_service),
        ]

        # Register all tools
        for tool in tools:
            self.register_tool(tool)

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a new tool in the registry."""
        self._tools[tool.name] = tool

    def get_llm_tools(self, session: Session) -> dict[str, LLMTool]:
        """Get LLM tools with both schemas and callables bound to session."""

        def create_tool_callable(tool: ToolDefinition) -> ToolCallable:
            async def tool_callable(params: dict[str, Any]) -> str:
                parsed_params = tool.parse_input(params)
                return await tool.handler(parsed_params, session)

            return tool_callable

        return {
            name: LLMTool(
                name=tool.name,
                description=tool.description,
                input_schema=tool.get_json_schema(),
                callable=create_tool_callable(tool),
            )
            for name, tool in self._tools.items()
        }

    def get_tool_names(self) -> list[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


_tools_registry: ToolsRegistry | None = None


def get_tools_registry(
    verification_service: PatientVerificationService | None = None,
    appointment_service: AppointmentService | None = None,
) -> ToolsRegistry:
    """Get or create tools registry instance."""
    global _tools_registry

    if _tools_registry is None:
        if not verification_service or not appointment_service:
            raise ValueError("Must provide services for initial registry creation")

        _tools_registry = ToolsRegistry(
            verification_service,
            appointment_service,
        )

    return _tools_registry
