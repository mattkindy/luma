"""Appointment management service interface and implementations."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass
class Appointment:
    """Appointment data model."""

    id: str
    patient_id: str
    date_time: datetime
    provider: str
    appointment_type: str
    status: str  # scheduled, confirmed, cancelled
    location: str


class AppointmentService(Protocol):
    """Interface for appointment management services."""

    async def get_appointments(self, patient_id: str) -> list[Appointment]:
        """Get all appointments for a patient.

        Args:
            patient_id: The patient's unique identifier

        Returns:
            List of appointments for the patient
        """
        ...

    async def confirm_appointment(self, patient_id: str, appointment_id: str) -> bool:
        """Confirm an appointment.

        Args:
            patient_id: The patient's unique identifier
            appointment_id: The appointment to confirm

        Returns:
            True if confirmation successful, False otherwise
        """
        ...

    async def cancel_appointment(self, patient_id: str, appointment_id: str) -> bool:
        """Cancel an appointment.

        Args:
            patient_id: The patient's unique identifier
            appointment_id: The appointment to cancel

        Returns:
            True if cancellation successful, False otherwise
        """
        ...


class InMemoryAppointmentService:
    """In-memory appointment service

    Uses mock appointment data stored in memory.
    """

    def __init__(self):
        """Initialize with mock appointment data."""
        self.appointments = self._create_mock_appointments()

    async def get_appointments(self, patient_id: str) -> list[Appointment]:
        """Get all appointments for a patient."""
        return [apt for apt in self.appointments if apt.patient_id == patient_id and apt.date_time > datetime.now(UTC)]

    async def confirm_appointment(self, patient_id: str, appointment_id: str) -> bool:
        """Confirm an appointment."""
        appointment = self._find_appointment(patient_id, appointment_id)
        if appointment and appointment.status == "scheduled":
            appointment.status = "confirmed"
            return True
        return False

    async def cancel_appointment(self, patient_id: str, appointment_id: str) -> bool:
        """Cancel an appointment."""
        appointment = self._find_appointment(patient_id, appointment_id)
        if appointment and appointment.status in ["scheduled", "confirmed"]:
            appointment.status = "cancelled"
            return True
        return False

    def _find_appointment(self, patient_id: str, appointment_id: str) -> Appointment | None:
        """Find a specific appointment for a patient."""
        for appointment in self.appointments:
            if appointment.patient_id == patient_id and appointment.id == appointment_id:
                return appointment
        return None

    def _create_mock_appointments(self) -> list[Appointment]:
        """Create mock appointment data for testing."""
        now = datetime.now(UTC)
        base_time = now.replace(
            year=now.year + 1 if now.month == 12 else now.year,
            month=1 if now.month == 12 else now.month + 1,
            day=8,
        )

        return [
            # Patient 1 (john_smith) appointments
            Appointment(
                id="APT_001",
                patient_id="PATIENT_001",
                date_time=base_time.replace(day=base_time.day + 1),
                provider="Dr. Sarah Johnson",
                appointment_type="Annual Physical",
                status="scheduled",
                location="Main Clinic - Room 101",
            ),
            Appointment(
                id="APT_002",
                patient_id="PATIENT_001",
                date_time=base_time.replace(day=base_time.day + 7, hour=14),
                provider="Dr. Mike Chen",
                appointment_type="Follow-up",
                status="scheduled",
                location="Main Clinic - Room 205",
            ),
            # Patient 2 (jane_doe) appointments
            Appointment(
                id="APT_003",
                patient_id="PATIENT_002",
                date_time=base_time.replace(day=base_time.day + 2, hour=10),
                provider="Dr. Emily Davis",
                appointment_type="Consultation",
                status="confirmed",
                location="West Clinic - Room 301",
            ),
            # Patient 3 (mike_johnson) appointments
            Appointment(
                id="APT_004",
                patient_id="PATIENT_003",
                date_time=base_time.replace(day=base_time.day + 5, hour=11),
                provider="Dr. Lisa Brown",
                appointment_type="Lab Results Review",
                status="scheduled",
                location="Main Clinic - Room 150",
            ),
            # Patient 4 (sarah_wilson) appointments
            Appointment(
                id="APT_005",
                patient_id="PATIENT_004",
                date_time=base_time.replace(day=base_time.day + 3, hour=15),
                provider="Dr. Robert Taylor",
                appointment_type="Specialist Referral",
                status="scheduled",
                location="East Clinic - Room 402",
            ),
        ]


class ProductionAppointmentService:
    """Production appointment service interface.

    This would integrate with actual scheduling systems like Epic MyChart,
    Cerner, or other EHR appointment management systems.
    """

    def __init__(self, scheduling_client):
        """Initialize with scheduling system client."""
        self.scheduling_client = scheduling_client

    async def get_appointments(self, patient_id: str) -> list[Appointment]:
        """Get appointments from production scheduling system."""
        # Future implementation would call:
        # return self.scheduling_client.get_patient_appointments(patient_id)
        raise NotImplementedError("Production appointment service not implemented yet")

    async def confirm_appointment(self, patient_id: str, appointment_id: str) -> bool:
        """Confirm appointment in production system."""
        # Future implementation would call:
        # return self.scheduling_client.confirm_appointment(patient_id, appointment_id)
        raise NotImplementedError("Production appointment service not implemented yet")

    async def cancel_appointment(self, patient_id: str, appointment_id: str) -> bool:
        """Cancel appointment in production system."""
        # Future implementation would call:
        # return self.scheduling_client.cancel_appointment(patient_id, appointment_id)
        raise NotImplementedError("Production appointment service not implemented yet")


appointment_service = InMemoryAppointmentService()
