"""Tool adaptations for LangGraph/LangChain compatibility."""

from langchain_core.tools import StructuredTool

from app.services.appointments import appointment_service
from app.services.session_manager import session_manager
from app.services.verification import verification_service
from app.tools.appointment_actions import create_cancel_appointment_tool, create_confirm_appointment_tool
from app.tools.list_appointments import create_list_appointments_tool
from app.tools.verify_patient import create_verify_patient_tool
from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_langgraph_tools(include_verification: bool = True, verification_only: bool = False) -> list[StructuredTool]:
    """Get all LangGraph-compatible tools for a session.

    Args:
        session_id: Current session ID
        include_verification: Whether to include verification tool
        verification_only: If True, only return verification tool

    Returns:
        List of StructuredTool instances
    """
    tools = []

    if verification_only:
        return [create_verify_patient_tool(verification_service, session_manager)]

    if include_verification:
        tools.append(create_verify_patient_tool(verification_service, session_manager))

    tools.extend(
        [
            create_list_appointments_tool(appointment_service),
            create_confirm_appointment_tool(appointment_service),
            create_cancel_appointment_tool(appointment_service),
        ]
    )

    return tools
