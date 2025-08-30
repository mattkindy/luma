"""API endpoints for the healthcare AI service."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.models.conversation import ConversationRequest, ConversationResponse, HealthResponse

router = APIRouter()


@router.post("/conversation", response_model=ConversationResponse, tags=["Conversation"])
async def handle_conversation(request: ConversationRequest) -> ConversationResponse:
    """Handle a conversation message and return AI response.

    This is a basic implementation with canned responses for initial setup.
    Will be replaced with actual Claude integration in Phase 1.
    """
    # Generate session ID if not provided
    session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"

    # Canned responses for testing
    canned_responses: dict[str, str] = {
        "hello": (
            "Hello! I'm your healthcare assistant. To help you with your appointments, "
            "I'll need to verify your identity first. Please provide your full name, "
            "phone number, and date of birth."
        ),
        "help": (
            "I can help you with managing your appointments, but first I need to verify "
            "your identity. Please provide your full name, phone number, and date of birth."
        ),
        "appointments": (
            "I'd be happy to help you with your appointments! However, I need to verify "
            "your identity first for security purposes. Please provide your full name, "
            "phone number, and date of birth."
        ),
    }

    # Simple keyword matching for canned responses
    message_lower = request.message.lower()

    if "hello" in message_lower or "hi" in message_lower:
        response_text = canned_responses["hello"]
    elif "help" in message_lower:
        response_text = canned_responses["help"]
    elif "appointment" in message_lower:
        response_text = canned_responses["appointments"]
    else:
        response_text = (
            "Hello! I'm your healthcare assistant. To help you with your appointments, "
            "I'll need to verify your identity first. Please provide your full name, "
            "phone number, and date of birth."
        )

    return ConversationResponse(response=response_text, session_id=session_id)


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", timestamp=datetime.now(UTC), version=__version__)
