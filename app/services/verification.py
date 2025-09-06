"""Patient verification service interface and implementations."""

import hashlib
from dataclasses import dataclass
from typing import ClassVar, Protocol

from app.models.patient import Patient


@dataclass
class VerificationInfo:
    """Patient verification information."""

    name: str
    phone: str
    date_of_birth: str

    def get_lookup_hash(self) -> str:
        """Generate hash for verification lookup."""
        # Normalize data for consistent hashing
        normalized_name = self.name.lower().strip().replace(r"[^a-zA-Z ]", "").replace(" ", "_")
        normalized_phone = "".join(filter(str.isdigit, self.phone))[-10:]  # Last 10 digits
        normalized_dob = self.date_of_birth.replace("/", "-").replace(".", "-")

        # Create lookup string
        lookup_string = f"{normalized_name}_{normalized_phone}_{normalized_dob}"

        # Return SHA256 hash (first 16 chars for readability)
        return hashlib.sha256(lookup_string.encode()).hexdigest()[:16]


class PatientVerificationService(Protocol):
    """Interface for patient verification services.

    This allows pluggable verification implementations:
    - Phase 1: Hardcoded test patients
    - Phase 2+: Integration with EHR systems, Epic, etc.
    """

    async def verify_patient(self, name: str, phone: str, date_of_birth: str) -> str | None:
        """Verify patient identity and return patient ID if successful.

        Args:
            name: Patient's full name
            phone: Patient's phone number
            date_of_birth: Patient's date of birth (YYYY-MM-DD format)

        Returns:
            Patient ID if verification successful, None otherwise
        """
        ...


class HardcodedVerificationService:
    """Hardcoded verification service for Phase 1 development.

    Uses predefined test patients for development and testing.
    """

    TEST_PATIENTS: ClassVar[list[Patient]] = [
        Patient(id="PATIENT_001", name="John Smith", phone="555-123-4567", date_of_birth="1980-01-01"),
        Patient(id="PATIENT_002", name="Jane Doe", phone="555-987-6543", date_of_birth="1985-05-15"),
        Patient(id="PATIENT_003", name="Mike Johnson", phone="555-555-1234", date_of_birth="1975-12-25"),
        Patient(id="PATIENT_004", name="Sarah Wilson", phone="555-444-3333", date_of_birth="1990-08-30"),
    ]

    def __init__(self):
        """Initialize with hash-based verification lookup."""
        self.verification_lookup: dict[str, Patient] = {}

        for patient in self.TEST_PATIENTS:
            lookup_hash = VerificationInfo(
                name=patient.name,
                phone=patient.phone,
                date_of_birth=patient.date_of_birth,
            ).get_lookup_hash()

            self.verification_lookup[lookup_hash] = patient

    async def verify_patient(self, name: str, phone: str, date_of_birth: str) -> str | None:
        """Verify patient using hash-based lookup.

        Args:
            name: Patient's full name
            phone: Patient's phone number
            date_of_birth: Patient's date of birth (YYYY-MM-DD format)

        Returns:
            Patient ID if found in test data, None otherwise
        """
        verification = VerificationInfo(
            name=name,
            phone=phone,
            date_of_birth=date_of_birth,
        )

        lookup_hash = verification.get_lookup_hash()

        patient = self.verification_lookup.get(lookup_hash)
        return patient.id if patient else None

    def _normalize_name(self, name: str) -> str:
        """Normalize name for consistent lookup."""
        return name.lower().strip().replace(" ", "_")

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for consistent lookup."""
        # Remove all non-digits
        digits_only = "".join(filter(str.isdigit, phone))

        # Handle different formats (add 1 if missing for US numbers)
        if len(digits_only) == 10:
            return digits_only

        if len(digits_only) == 11 and digits_only.startswith("1"):
            return digits_only[1:]  # Remove country code

        return digits_only

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date for consistent lookup."""
        # Remove any separators and standardize format
        cleaned = date_str.replace("/", "-").replace(".", "-")

        # Handle different date formats
        parts = cleaned.split("-")
        if len(parts) == 3:
            # Assume YYYY-MM-DD, MM-DD-YYYY, or DD-MM-YYYY
            if len(parts[0]) == 4:  # YYYY-MM-DD
                return cleaned

            if len(parts[2]) == 4:  # MM-DD-YYYY or DD-MM-YYYY
                # Assume MM-DD-YYYY (US format)
                return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"

        return cleaned


class ProductionVerificationService:
    """Production verification service interface.

    This would integrate with actual EHR systems like Epic, Cerner, etc.
    Currently just a placeholder for future implementation.
    """

    def __init__(self, ehr_client):
        """Initialize with EHR system client."""
        self.ehr_client = ehr_client

    async def verify_patient(self, name: str, phone: str, date_of_birth: str) -> str | None:
        """Verify patient using production EHR system.

        This would make actual API calls to the EHR system for patient matching.
        """
        # Future implementation would call:
        # return await self.ehr_client.patient_match(name=name, phone=phone, dob=date_of_birth)
        raise NotImplementedError("Production verification not implemented yet")


verification_service = HardcodedVerificationService()
