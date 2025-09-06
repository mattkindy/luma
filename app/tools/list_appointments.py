"""List appointments tool."""

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel

from app.graphs.state import ConversationState
from app.services.appointments import AppointmentService


class EmptyInputWithState(BaseModel):
    """Empty input schema for tools that don't require parameters."""

    state: Annotated[ConversationState, InjectedState]


def create_list_appointments_tool(appointment_service: AppointmentService):
    @tool("list_appointments", parse_docstring=True, args_schema=EmptyInputWithState)
    async def list_appointments_handler(state: Annotated[ConversationState, InjectedState]) -> str:
        """List all upcoming appointments for the verified patient.

        PREREQUISITE: Patient must be verified first using verify_patient tool.

        Purpose: Display all scheduled, confirmed, and upcoming appointments

        Parameters: None (uses verified patient's information automatically)

        Example Usage:
        - User says: "Show me my appointments" or "What appointments do I have?"
        - Call: list_appointments() (no parameters needed)
        - Provide the output back to the patient.

        Response Format: Returns formatted list showing:
        - Appointment ID (e.g., APT_001) - needed for confirm/cancel actions
        - Date and time in readable format
        - Provider name
        - Appointment type (Annual Physical, Follow-up, etc.)
        - Current status (scheduled, confirmed, cancelled)
        - Location/room information

        Success Response: Returns formatted list showing the patient's upcoming appointments.
        Failure Response: Returns error message asking to check information

        Important Notes:
        - Will return error if patient not verified
        - Shows appointments in chronological order
        - Includes appointment IDs that can be used with confirm/cancel tools
        - Only shows future appointments, not past ones
        """
        if not state.patient_info.verified or not state.patient_info.patient_id:
            return "Please verify the patient's identity first before accessing appointment information."

        appointments = await appointment_service.get_appointments(state.patient_info.patient_id)

        if not appointments:
            return "The patient has no upcoming appointments scheduled."

        result = "Here are the patient's upcoming appointments:\n\n"
        for apt in appointments:
            status_emoji = "✅" if apt.status == "confirmed" else "📅" if apt.status == "scheduled" else "❌"
            result += f"{status_emoji} **{apt.id}** - {apt.date_time.strftime('%A, %B %d, %Y at %I:%M %p')}\n"
            result += f"   Provider: {apt.provider}\n"
            result += f"   Type: {apt.appointment_type}\n"
            result += f"   Status: {apt.status.title()}\n"
            result += f"   Location: {apt.location}\n\n"

        result += "The patient can confirm or cancel any scheduled appointment by providing the appointment ID."
        return result.strip()

    return list_appointments_handler
