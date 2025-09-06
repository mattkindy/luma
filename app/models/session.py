"""Session and state management models."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Session:
    """Session state for conversation management."""

    session_id: str
    patient_id: str | None = None
    verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    failed_verification_attempts: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Return the session as a dictionary."""
        return {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "verified": self.verified,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "failed_verification_attempts": self.failed_verification_attempts,
        }

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now(UTC)

    def set_verified(self, patient_id: str) -> None:
        """Mark session as verified with patient ID."""
        logger.info(f"Setting session {self.session_id} as verified with patient ID {patient_id}")
        self.verified = True
        self.patient_id = patient_id
        self.update_activity()

    def increment_failed_attempts(self) -> None:
        """Increment failed verification attempts."""
        self.failed_verification_attempts += 1
        self.update_activity()


class VerificationRequest(BaseModel):
    """Request model for patient verification."""

    name: str
    phone: str
    date_of_birth: str


class VerificationResponse(BaseModel):
    """Response model for patient verification."""

    success: bool
    message: str
    session_id: str


class AppointmentListResponse(BaseModel):
    """Response model for appointment listing."""

    appointments: list[dict[str, Any]]
    session_id: str


class AppointmentActionRequest(BaseModel):
    """Request model for appointment actions (confirm/cancel)."""

    appointment_id: str


class AppointmentActionResponse(BaseModel):
    """Response model for appointment actions."""

    success: bool
    message: str
    session_id: str


class ToolCallResult(BaseModel):
    """Result of a tool call execution."""

    success: bool
    result: Any
    error_message: str | None = None
