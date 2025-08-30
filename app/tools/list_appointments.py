"""List appointments tool."""

from pydantic import BaseModel

from app.models.session import Session
from app.services.appointments import AppointmentService
from app.tools.base import ToolDefinition


class EmptyInput(BaseModel):
    """Empty input schema for tools that don't require parameters."""


async def list_appointments_handler(
    params: BaseModel, session: Session, appointment_service: AppointmentService
) -> str:
    """Handle list appointments tool call."""
    if not session.verified or not session.patient_id:
        return "Please verify the patient's identity first before accessing appointment information."

    appointments = await appointment_service.get_appointments(session.patient_id)

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


def create_list_appointments_tool(appointment_service: AppointmentService) -> ToolDefinition:
    """Create list appointments tool with bound appointment service."""
    return ToolDefinition(
        name="list_appointments",
        description="""List all upcoming appointments for the verified patient.

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
        """,
        input_schema_class=EmptyInput,
        handler=lambda params, session: list_appointments_handler(params, session, appointment_service),
    )
