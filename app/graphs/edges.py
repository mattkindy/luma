"""Edge logic and routing for the conversation graph."""

from typing import Literal

from app.graphs.state import ConversationState
from app.utils.logging import get_logger

logger = get_logger(__name__)


def route_agent_output(state: ConversationState) -> Literal["agent", "tools", "verify", "error", "end"]:
    """Route from agent node based on state.

    Determines the next node based on:
    1. Explicit next_step if set
    2. Presence of pending tool calls
    3. Error conditions
    4. Default to end
    """
    logger.debug(f"Routing from agent node. Next step: {state.next_step}")

    if state.next_step:
        return state.next_step

    if state.error:
        logger.warning(f"Routing to error handler due to: {state.error}")
        return "error"

    if state.pending_tool_calls:
        needs_verification = _check_needs_verification_routing(state)
        if needs_verification:
            return "verify"
        return "tools"

    return "end"


def route_tool_output(state: ConversationState) -> Literal["agent", "error"]:
    """Route from tool execution node.

    Always returns to agent unless there's an error.
    """
    if state.error:
        return "error"
    return "agent"


def route_verification_output(state: ConversationState) -> Literal["agent", "error"]:
    """Route from verification node.

    Returns to agent for next action after verification attempt.
    """
    if state.error:
        return "error"
    return "agent"


def route_error_output(state: ConversationState) -> Literal["agent", "end"]:
    """Route from error handler.

    Decides whether to retry (back to agent) or end conversation.
    """
    if state.retry_count >= 3:
        logger.warning(f"Max retries ({state.retry_count}) reached, ending conversation")
        return "end"

    if not state.error:
        return "agent"

    return "end"


def should_continue(state: ConversationState) -> bool:
    """Determine if conversation should continue.

    Used for cycle detection and conversation limits.
    """
    if len(state.messages) > 100:
        logger.warning("Conversation exceeded 100 messages")
        return False

    if state.retry_count > 5:
        logger.warning("Too many retries")
        return False

    return True


def _check_needs_verification_routing(state: ConversationState) -> bool:
    """Check if verification is needed for pending tool calls."""
    if state.patient_info.verified:
        return False

    # Tools that require verification
    protected_tools = {
        "list_appointments",
        "confirm_appointment",
        "cancel_appointment",
    }

    for tool_call in state.pending_tool_calls:
        if tool_call.name in protected_tools:
            logger.info(f"Tool {tool_call.name} requires patient verification")
            return True

        if tool_call.name == "verify_patient":
            # Verification tool itself should go to verify node
            return True

    return False
