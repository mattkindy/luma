"""Conversation service for managing conversation flow."""

from datetime import datetime
from typing import Any

from app.models.llm import LLMMessage
from app.models.session import Session
from app.services.llm import LLMService
from app.tools.registry import ToolsRegistry
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConversationService:
    """Service for handling conversational AI interactions."""

    def __init__(
        self,
        llm_service: LLMService,
        tools_registry: ToolsRegistry,
    ):
        """Initialize conversation service with dependencies."""
        self.llm_service = llm_service
        self.tools_registry = tools_registry

    async def process_message(self, message: str, session: Session) -> str:
        """Process a user message and return AI response.

        Args:
            message: User's message
            session: Current session state

        Returns:
            AI assistant's response
        """
        logger.info(f"Processing message for session {session.session_id}")
        session.add_message("user", message)
        messages = self._build_conversation_context(session)

        llm_tools = self.tools_registry.get_llm_tools(session)
        logger.info(f"Available tools: {list(llm_tools.keys())}")

        try:
            logger.info("Executing agent loop")
            result = await self.llm_service.execute_agent_loop(
                messages=messages,
                system_prompt=self._get_system_prompt(session),
                tools=llm_tools,
                max_turns=5,
            )

            logger.info(f"Agent loop completed in {result.turns} turns, stop_reason: {result.stop_reason}")

            final_text = self._extract_text_from_content(result.content)

            if final_text:
                logger.info(f"Extracted final text: {final_text[:100]}...")
                session.add_message("assistant", final_text)
                return final_text

        except Exception as e:
            logger.error(f"Conversation processing failed: {e}", exc_info=True)
            error_msg = "I apologize, but I'm experiencing technical difficulties. Please try again."
            session.add_message("assistant", error_msg)
            return error_msg

        # Fallback response
        fallback_msg = "I'm here to help with your appointments. Could you please rephrase your request?"
        session.add_message("assistant", fallback_msg)
        return fallback_msg

    def _build_conversation_context(self, session: Session) -> list[LLMMessage]:
        """Build conversation context for LLM."""
        messages = []
        for msg in session.conversation_history:
            if msg.role in ["user", "assistant"]:
                messages.append(LLMMessage(role=msg.role, content=msg.content))
        return messages

    def _get_system_prompt(self, session: Session) -> str:
        """Get system prompt based on session state."""
        base_prompt = """You are a helpful healthcare assistant for appointment management.

Your primary responsibilities:
1. Verify patient identity before providing appointment information
2. Help patients list, confirm, and cancel appointments
3. Provide clear, professional, and empathetic responses

IMPORTANT SECURITY RULES:
- NEVER provide appointment information without successful identity verification
- Always verify identity using full name, phone number, and date of birth
- Use the verify_patient tool for identity verification
- Only use appointment tools AFTER successful verification

Current session status:"""

        if session.verified and session.patient_id:
            base_prompt += f"\n- Patient verified: YES (Patient ID: {session.patient_id})"
            base_prompt += "\n- Appointment tools: AVAILABLE"
        else:
            base_prompt += "\n- Patient verified: NO"
            base_prompt += "\n- Appointment tools: NOT AVAILABLE (verification required)"

        if session.failed_verification_attempts > 0:
            base_prompt += f"\n- Failed verification attempts: {session.failed_verification_attempts}"

        base_prompt += f"\nCurrent date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return base_prompt

    def _extract_text_from_content(self, content: list[Any]) -> str | None:
        """Extract text content from Claude response."""
        for block in content:
            if (hasattr(block, "type") and block.type == "text") or hasattr(block, "text"):
                return block.text

        return None
