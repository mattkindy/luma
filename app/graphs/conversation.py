"""Main conversation graph implementation."""

from typing import Any

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.graphs.edges import (
    route_agent_output,
    route_error_output,
    route_tool_output,
    route_verification_output,
)
from app.graphs.nodes import agent_node, error_handler_node, verify_patient_node
from app.graphs.state import ConversationState
from app.graphs.tools import get_langgraph_tools
from app.utils.logging import get_logger

logger = get_logger(__name__)


def create_conversation_graph(checkpointer=None):
    """Create the main conversation graph.

    This graph orchestrates the entire conversation flow including:
    - Agent reasoning and response generation
    - Tool execution
    - Patient verification
    - Error handling and recovery

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Creating conversation graph")

    workflow = StateGraph(ConversationState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(get_langgraph_tools(include_verification=False)))
    workflow.add_node("verify", verify_patient_node)
    workflow.add_node("error", error_handler_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        route_agent_output,
        {
            "tools": "tools",
            "verify": "verify",
            "error": "error",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "tools",
        route_tool_output,
        {
            "agent": "agent",
            "error": "error",
        },
    )

    workflow.add_conditional_edges(
        "verify",
        route_verification_output,
        {
            "agent": "agent",
            "error": "error",
        },
    )

    workflow.add_conditional_edges(
        "error",
        route_error_output,
        {
            "agent": "agent",
            "end": END,
        },
    )

    compiled = workflow.compile(checkpointer=checkpointer or MemorySaver())

    logger.info("Conversation graph created successfully")
    return compiled


def get_system_prompt(patient_verified: bool = False, patient_id: str | None = None) -> str:
    """Generate system prompt based on session state.

    Args:
        session_id: Current session ID
        patient_verified: Whether patient is verified
        patient_id: Patient ID if verified

    Returns:
        System prompt string
    """
    from datetime import datetime

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

    if patient_verified and patient_id:
        base_prompt += f"\n- Patient verified: YES (Patient ID: {patient_id})"
        base_prompt += "\n- Appointment tools: AVAILABLE"
    else:
        base_prompt += "\n- Patient verified: NO"
        base_prompt += "\n- Appointment tools: NOT AVAILABLE (verification required)"

    base_prompt += f"\n- Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return base_prompt


def create_initial_state(
    message: str, session_id: str, patient_info: dict[str, Any] | None = None
) -> ConversationState:
    """Create initial conversation state.

    Args:
        message: User's message
        session_id: Session identifier
        patient_info: Optional patient verification info

    Returns:
        Initial ConversationState
    """
    from langchain_core.messages import HumanMessage

    from app.graphs.state import PatientInfo

    if patient_info:
        patient = PatientInfo(
            patient_id=patient_info.get("patient_id"),
            verified=patient_info.get("verified", False),
            failed_attempts=patient_info.get("failed_attempts", 0),
        )
    else:
        patient = PatientInfo()

    system_prompt = get_system_prompt(patient.verified, patient.patient_id)

    return ConversationState(
        messages=[
            SystemMessage(content=system_prompt),
            HumanMessage(content=message),
        ],
        session_id=session_id,
        patient_info=patient,
        pending_tool_calls=[],
        tool_results=[],
        next_step=None,
        error=None,
        retry_count=0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
    )


class ConversationGraphManager:
    """Manager class for conversation graph operations."""

    def __init__(self, checkpointer=None):
        """Initialize the conversation graph manager.

        Args:
            checkpointer: Optional checkpointer for state persistence
        """
        self.graph = create_conversation_graph(checkpointer)
        self.checkpointer = checkpointer or MemorySaver()

    async def process_message(
        self, message: str, session_id: str, patient_info: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process a user message through the conversation graph.

        Args:
            message: User's message
            session_id: Session identifier
            patient_info: Optional patient verification info

        Returns:
            Processing result with response and metadata
        """
        logger.info(f"Processing message for session {session_id}")

        initial_state = create_initial_state(message, session_id, patient_info)

        config = {
            "configurable": {
                "thread_id": session_id,
                "session_id": session_id,
            },
            "recursion_limit": 10,  # Prevent infinite loops
        }

        try:
            result = await self.graph.ainvoke(
                initial_state.model_dump(),
                config,
            )

            if result.get("messages"):
                last_message = result["messages"][-1]
                response_text = last_message.content if hasattr(last_message, "content") else str(last_message)
            else:
                response_text = "I apologize, but I couldn't generate a response. Please try again."

            metadata = {
                "session_id": session_id,
                "total_input_tokens": result.get("total_input_tokens", 0),
                "total_output_tokens": result.get("total_output_tokens", 0),
                "cache_read_tokens": result.get("cache_read_tokens", 0),
                "cache_creation_tokens": result.get("cache_creation_tokens", 0),
            }

            return {"response": response_text, "metadata": metadata}

        except Exception as e:
            logger.error(f"Graph execution error: {e}", exc_info=True)
            return {
                "response": "I apologize, but I encountered an error. Please try again.",
                "metadata": {"error": str(e), "session_id": session_id},
            }
