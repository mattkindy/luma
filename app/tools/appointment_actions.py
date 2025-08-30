"""Appointment confirmation and cancellation tools."""

from pydantic import BaseModel, Field

from app.models.session import Session
from app.services.appointments import AppointmentService
from app.tools.base import ToolDefinition


class AppointmentActionInput(BaseModel):
    """Input schema for appointment actions (confirm/cancel)."""

    appointment_id: str = Field(
        ...,
        description="The exact appointment ID (e.g., APT_001, APT_002)",
        pattern=r"^APT_[0-9]{3}$",
        min_length=1,
        max_length=50,
        examples=["APT_001", "APT_002"],
    )


async def confirm_appointment_handler(
    params: BaseModel, session: Session, appointment_service: AppointmentService
) -> str:
    """Handle confirm appointment tool call."""
    if not session.verified or not session.patient_id:
        return "Please verify the patient's identity first before accessing appointment information."

    action_input = (
        params if isinstance(params, AppointmentActionInput) else AppointmentActionInput.model_validate(params)
    )

    success = await appointment_service.confirm_appointment(session.patient_id, action_input.appointment_id)

    if success:
        return f"Appointment {action_input.appointment_id} has been confirmed successfully!"

    return (
        f"Unable to confirm appointment {action_input.appointment_id}. "
        "It may not exist, already be confirmed, or be cancelled."
    )


async def cancel_appointment_handler(
    params: BaseModel, session: Session, appointment_service: AppointmentService
) -> str:
    """Handle cancel appointment tool call."""
    if not session.verified or not session.patient_id:
        return "Please verify the patient's identity first before accessing appointment information."

    action_input = (
        params if isinstance(params, AppointmentActionInput) else AppointmentActionInput.model_validate(params)
    )

    success = await appointment_service.cancel_appointment(session.patient_id, action_input.appointment_id)

    if success:
        return f"Appointment {action_input.appointment_id} has been cancelled successfully."
    else:
        return f"Unable to cancel appointment {action_input.appointment_id}. It may not exist or already be cancelled."


def create_confirm_appointment_tool(appointment_service: AppointmentService) -> ToolDefinition:
    """Create confirm appointment tool with bound appointment service."""
    return ToolDefinition(
        name="confirm_appointment",
        description="""Confirm a scheduled appointment for the verified patient.

        PREREQUISITE: Patient must be verified first using verify_patient tool.

        Purpose: Change appointment status from 'scheduled' to 'confirmed'

        Required Information:
        - appointment_id: The exact appointment ID (e.g., APT_001, APT_002)

        Example Usage:
        - User says: "Confirm my appointment APT_001" or "I want to confirm appointment APT_001"
        - Call: confirm_appointment(appointment_id="APT_001")
        - Provide the output back to the patient.

        Example Usage 2:
        - User says: "Confirm my appointment on Friday"
        - Lookup appointment by date: find appointment ID "APT_512" via list_appointments tool
        - Call: confirm_appointment(appointment_id="APT_512")
        - Provide the output back to the patient.

        Success Response: Confirmation message with appointment ID
        Failure Response: Error if appointment doesn't exist, already confirmed, or cancelled

        Important Notes:
        - Only works with 'scheduled' appointments (not already confirmed or cancelled)
        - Appointment ID must be exact match (case-sensitive)
        - Can retrieve appointment IDs from list_appointments tool first
        - Patient does not need to specify the id explicitly if they can identify the appointment in another way
        - Cannot confirm appointments for other patients (enforced by verification)

        Common Errors:
        - "APT_001 not found" - Invalid appointment ID
        - "Already confirmed" - Appointment was previously confirmed
        - "Cannot confirm cancelled appointment" - Appointment was cancelled
        """,
        input_schema_class=AppointmentActionInput,
        handler=lambda params, session: confirm_appointment_handler(params, session, appointment_service),
    )


def create_cancel_appointment_tool(appointment_service: AppointmentService) -> ToolDefinition:
    """Create cancel appointment tool with bound appointment service."""
    return ToolDefinition(
        name="cancel_appointment",
        description="""Cancel a scheduled or confirmed appointment for the verified patient.

        PREREQUISITE: Patient must be verified first using verify_patient tool.

        Purpose: Cancel an existing appointment (scheduled or confirmed status)

        Required Information:
        - appointment_id: The exact appointment ID (e.g., APT_001, APT_002)

        Example Usage:
        - User says: "Cancel my appointment APT_001" or "I need to cancel APT_002"
        - Call: cancel_appointment(appointment_id="APT_001")
        - Provide the output back to the patient.

        Example Usage 2:
        - User says: "Cancel my appointment on March 1st 2025"
        - Lookup appointment by date: find appointment ID "APT_003" via list_appointments tool
        - Call: cancel_appointment(appointment_id="APT_003")
        - Provide the output back to the patient.

        Success Response: Cancellation confirmation with appointment ID
        Failure Response: Error if appointment doesn't exist or already cancelled

        Important Notes:
        - Works with both 'scheduled' and 'confirmed' appointments
        - Cannot cancel appointments that are already cancelled
        - Appointment ID must be exact match (case-sensitive)
        - Can retrieve appointment IDs from list_appointments tool first
        - Patient does not need to specify the id explicitly if they can identify the appointment in another way
        - Cannot cancel appointments for other patients (enforced by verification)
        - Cancelled appointments cannot be un-cancelled (would need to reschedule)

        Common Errors:
        - "APT_001 not found" - Invalid appointment ID
        - "Already cancelled" - Appointment was previously cancelled
        - "Cannot cancel past appointment" - Appointment date has passed
        """,
        input_schema_class=AppointmentActionInput,
        handler=lambda params, session: cancel_appointment_handler(params, session, appointment_service),
    )
