"""Appointment confirmation and cancellation tools."""

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from app.graphs.state import ConversationState
from app.services.appointments import AppointmentService


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

    state: Annotated[ConversationState, InjectedState]


def create_confirm_appointment_tool(appointment_service: AppointmentService):
    @tool("confirm_appointment", parse_docstring=True, args_schema=AppointmentActionInput)
    async def confirm_appointment_handler(
        appointment_id: str, state: Annotated[ConversationState, InjectedState]
    ) -> str:
        """Confirm a scheduled appointment for the verified patient.

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
        """
        if not state.patient_info.verified or not state.patient_info.patient_id:
            return "Please verify the patient's identity first before accessing appointment information."

        success = await appointment_service.confirm_appointment(
            state.patient_info.patient_id,
            appointment_id,
        )

        if success:
            return f"Appointment {appointment_id} has been confirmed successfully!"

        return (
            f"Unable to confirm appointment {appointment_id}. It may not exist, already be confirmed, or be cancelled."
        )

    return confirm_appointment_handler


def create_cancel_appointment_tool(appointment_service: AppointmentService):
    @tool("cancel_appointment", parse_docstring=True, args_schema=AppointmentActionInput)
    async def cancel_appointment_handler(
        appointment_id: str, state: Annotated[ConversationState, InjectedState]
    ) -> str:
        """Cancel a scheduled or confirmed appointment for the verified patient.

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
        """
        if not state.patient_info.verified or not state.patient_info.patient_id:
            return "Please verify the patient's identity first before accessing appointment information."

        success = await appointment_service.cancel_appointment(state.patient_info.patient_id, appointment_id)

        if success:
            return f"Appointment {appointment_id} has been cancelled successfully."

        return f"Unable to cancel appointment {appointment_id}. It may not exist or already be cancelled."

    return cancel_appointment_handler
