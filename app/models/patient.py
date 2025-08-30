"""Patient data models."""

from dataclasses import dataclass


@dataclass
class Patient:
    """Patient business model."""

    id: str
    name: str
    phone: str
    date_of_birth: str
