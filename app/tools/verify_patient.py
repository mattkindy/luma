"""Patient verification tool."""

import re
from datetime import datetime
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field, field_validator

from app.graphs.state import ConversationState
from app.services.session_manager import InMemorySessionManager
from app.services.verification import PatientVerificationService


class VerifyPatientInput(BaseModel):
    """Input schema for patient verification tool."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Patient's full legal name (first and last name)",
        examples=["John Smith", "Mary Jane Johnson"],
    )
    phone: str = Field(
        ...,
        pattern=r"^\d{3}-\d{3}-\d{4}$",
        description="Patient's phone number in xxx-xxx-xxxx format",
        examples=["555-123-4567", "800-555-1234"],
    )
    date_of_birth: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Patient's date of birth in YYYY-MM-DD format",
        examples=["1980-01-01", "1985-12-25"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate patient name format."""
        if not v or v.isspace():
            raise ValueError("Name cannot be empty or whitespace only")

        # Check for at least first and last name
        name_parts = v.strip().split()
        if len(name_parts) < 2:
            raise ValueError("Please provide both first and last name")

        # Check for valid characters (letters, spaces, hyphens, apostrophes, periods)
        # Note: May need special handling for unicode characters in the future
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", v):
            raise ValueError("Name can only contain letters, spaces, hyphens, apostrophes, and periods")

        return v.strip().title()  # Normalize to title case

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: str) -> str:
        """Validate date of birth format and reasonableness."""
        try:
            # Parse the date to ensure it's valid
            birth_date = datetime.strptime(v, "%Y-%m-%d")

            # Check if date is reasonable (not in future, not too old)
            today = datetime.now()
            age_years = (today - birth_date).days / 365.25

            if birth_date > today:
                raise ValueError("Date of birth cannot be in the future")

            if age_years > 150:
                raise ValueError("Date of birth seems too far in the past")

            if age_years < 0:
                raise ValueError("Invalid date of birth")

            return v

        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError("Date must be in YYYY-MM-DD format (e.g., 1980-01-01)") from e
            raise


def create_verify_patient_tool(
    verification_service: PatientVerificationService, session_manager: InMemorySessionManager
):
    @tool("verify_patient", parse_docstring=True, args_schema=VerifyPatientInput)
    async def verify_patient_handler(  # noqa: RUF029
        name: str, phone: str, date_of_birth: str, state: Annotated[ConversationState, InjectedState]
    ) -> str:
        """Verify a patient's identity before providing any appointment information.

        CRITICAL: This tool MUST be called before any appointment-related actions.

        Purpose: Authenticate patient using their personal information

        Required Information:
        - name: Patient's full legal name (first and last name, exactly as in medical records)
        - phone: Patient's primary phone number (any format: xxx-xxx-xxxx, (xxx) xxx-xxxx, or xxxxxxxxxx)
        - date_of_birth: Patient's birth date in YYYY-MM-DD format (e.g., 1980-01-01)

        Example Usage:
        - User says: "My name is John Smith, phone 555-123-4567, born January 1st 1980"
        - Call: verify_patient(name="John Smith", phone="555-123-4567", date_of_birth="1980-01-01")

        Success Response: Returns confirmation message and enables appointment tools
        Failure Response: Returns error message asking to check information

        Important Notes:
        - Phone number format must be xxx-xxx-xxxx (US format)
        - Date format must be YYYY-MM-DD
        - Name matching is case-insensitive
        - Only call this tool ONCE per conversation unless verification fails
        """
        # This is actually implemented as the `verify` node in the graph.
        return ""

    return verify_patient_handler
