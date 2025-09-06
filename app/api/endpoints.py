"""API endpoints for the healthcare AI service."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app import __version__
from app.models.conversation import ConversationRequest, ConversationResponse, HealthResponse
from app.services.conversation import conversation_service
from app.services.session_manager import session_manager
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/conversation", response_model=ConversationResponse, tags=["Conversation"])
async def handle_conversation(request: ConversationRequest) -> ConversationResponse:
    """Handle a conversation message and return AI response.

    This is a basic implementation with canned responses for initial setup.
    Will be replaced with actual Claude integration in Phase 1.
    """
    # Get or create session using session manager
    try:
        if request.session_id:
            logger.info(f"Validating existing session: {request.session_id}")
            session = session_manager.get_session(request.session_id)
            if not session:
                logger.warning(f"Invalid session ID provided: {request.session_id}")
                raise HTTPException(status_code=400, detail=f"Invalid session ID: {request.session_id}")
        else:
            logger.info("Creating new session")
            session = session_manager.get_or_create_session()

        session_id = session.session_id
        logger.info(f"Using session: {session_id}, verified: {session.verified}")

    except Exception as e:
        logger.error(f"Session management error: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Failed to manage session") from e

    try:
        logger.info(f"Processing message for session {session_id}: {request.message[:50]}...")
        response_text = await conversation_service.process_message(request.message, session)
        logger.info(f"Generated response for session {session_id}: {response_text[:50]}...")
        return ConversationResponse(response=response_text, session_id=session_id)
    except ValueError as e:
        # Handle token validation errors with specific HTTP status
        logger.warning(f"Message validation error for session {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Conversation processing error for session {session_id}: {e}", exc_info=True)
        error_msg = "I apologize, but I'm experiencing technical difficulties. Please try again."
        return ConversationResponse(response=error_msg, session_id=session_id)


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        version=__version__,
    )
