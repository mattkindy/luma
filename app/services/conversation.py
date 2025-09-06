"""Conversation service for managing conversation flow using LangGraph."""

import json

from app.graphs.conversation import ConversationGraphManager
from app.models.session import Session
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConversationService:
    """Service for handling conversational AI interactions using LangGraph.

    This service maintains the same interface as the original but uses
    LangGraph for orchestration under the hood.
    """

    def __init__(self):
        """Initialize conversation service.

        Args:
            llm_service: Legacy parameter, kept for compatibility
            tools_registry: Legacy parameter, kept for compatibility
        """
        self.graph_manager = ConversationGraphManager()

        logger.info("ConversationService initialized with LangGraph")

    async def process_message(self, message: str, session: Session) -> str:
        """Process a user message and return AI response.

        Args:
            message: User's message
            session: Current session state

        Returns:
            AI assistant's response

        Raises:
            ValueError: If message exceeds token limit
        """
        logger.info(
            f"Processing message for session {session.session_id} via LangGraph {json.dumps(session.as_dict())}"
        )

        try:
            self._validate_message_tokens(message)

            patient_info = {
                "patient_id": session.patient_id,
                "verified": session.verified,
                "failed_attempts": session.failed_verification_attempts,
            }

            result = await self.graph_manager.process_message(
                message=message,
                session_id=session.session_id,
                patient_info=patient_info,
            )

            response_text = result.get("response", "I apologize, but I couldn't process your request.")
            metadata = result.get("metadata", {})

            if metadata.get("total_input_tokens"):
                logger.info(
                    f"Token usage - Input: {metadata['total_input_tokens']}, "
                    f"Output: {metadata['total_output_tokens']}, "
                    f"Cache hits: {metadata.get('cache_read_tokens', 0)}"
                )

            return response_text

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"LangGraph processing failed: {e}", exc_info=True)
            error_msg = "I apologize, but I'm experiencing technical difficulties. Please try again."
            return error_msg

    def _validate_message_tokens(self, message: str) -> None:
        """Validate message doesn't exceed token limits.

        This maintains compatibility with existing token validation.

        Args:
            message: Message to validate

        Raises:
            ValueError: If message exceeds token limit
        """
        # Simple length-based validation (replace with actual tokenizer if needed)
        MAX_MESSAGE_CHARS = 4000  # Roughly 1000 tokens
        if len(message) > MAX_MESSAGE_CHARS:
            max_message_tokens = 1000  # For error message compatibility
            raise ValueError(f"Your message is too long. Please keep messages under {max_message_tokens} tokens.")


conversation_service = ConversationService()
