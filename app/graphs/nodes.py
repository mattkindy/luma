"""Node implementations for the conversation graph."""

import json
import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool

from app.graphs.state import ConversationState, PatientInfo, ToolCall
from app.graphs.tools import get_langgraph_tools
from app.services.session_manager import session_manager
from app.services.verification import verification_service
from app.tools.verify_patient import VerifyPatientInput
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def agent_node(state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
    """Main agent node that processes messages and decides on actions.

    This node:
    1. Determines available tools based on verification state
    2. Calls the LLM with appropriate tools
    3. Processes the response and determines next steps
    """
    logger.info(f"Agent node processing for session {state.session_id}")

    tools = _get_available_tools()

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    model = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0,
        max_tokens=4096,
        anthropic_api_key=api_key,
    )

    if tools:
        model = model.bind_tools(tools)

    try:
        system_message = next(m for m in state.messages if m.type == "system")
        non_system_messages = [m for m in state.messages if m.type != "system"]

        state.messages = [system_message, *non_system_messages]

        logger.debug(f"State messages: {json.dumps([m.model_dump() for m in state.messages], indent=4)}")
        logger.debug(f"State patient info: {state.patient_info.model_dump()}")

        response = await model.ainvoke(state.messages, config)

        logger.debug(f"Response: {json.dumps(response.model_dump(), indent=4)}")

        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            usage = metadata.get("usage", {})
            token_updates = {
                "total_input_tokens": state.total_input_tokens + usage.get("input_tokens", 0),
                "total_output_tokens": state.total_output_tokens + usage.get("output_tokens", 0),
            }

            # Handle cache tokens if present
            if "cache_creation_input_tokens" in usage:
                token_updates["cache_creation_tokens"] = (
                    state.cache_creation_tokens + usage["cache_creation_input_tokens"]
                )
            if "cache_read_input_tokens" in usage:
                token_updates["cache_read_tokens"] = state.cache_read_tokens + usage["cache_read_input_tokens"]
        else:
            token_updates = {}

        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(f"Agent requesting {len(response.tool_calls)} tool calls")
            tool_calls = [ToolCall(id=tc["id"], name=tc["name"], args=tc["args"]) for tc in response.tool_calls]
            return {
                "messages": [response],
                "pending_tool_calls": tool_calls,
                "next_step": "verify" if any(tc.name == "verify_patient" for tc in tool_calls) else "tools",
                **token_updates,
            }

        # No tool calls, regular response
        return {"messages": [response], "next_step": "end", **token_updates}

    except Exception as e:
        logger.error(f"Agent node error: {e}", exc_info=True)
        return {
            "error": str(e),
            "next_step": "error",
        }


async def verify_patient_node(state: ConversationState) -> dict[str, Any]:
    """Handle patient verification.

    This node specifically handles the verification flow,
    updating patient info based on verification results.
    """
    logger.info(f"Processing patient verification for session {state.session_id}")

    verify_call = next((tc for tc in state.pending_tool_calls if tc.name == "verify_patient"), None)

    if not verify_call:
        return {
            "error": "No verification tool call found",
            "next_step": "error",
        }

    remaining_tool_calls = [tc for tc in state.pending_tool_calls if tc.id != verify_call.id]

    try:
        verify_input = VerifyPatientInput.model_validate(verify_call.args)
        patient_id = await verification_service.verify_patient(
            verify_input.name,
            verify_input.phone,
            verify_input.date_of_birth,
        )

        if patient_id:
            logger.info(f"Patient verified successfully: {patient_id}")
            session = session_manager.get_session(state.session_id)
            if session is None:
                return {
                    "error": "Session not found",
                    "next_step": "error",
                }
            session.set_verified(patient_id)

            updated_info = PatientInfo(
                patient_id=patient_id,
                verified=True,
                failed_attempts=state.patient_info.failed_attempts,
            )

            success_message = "Identity verified successfully! You can now access your appointment information."

            return {
                "patient_info": updated_info,
                "messages": [
                    ToolMessage(
                        content=success_message,
                        tool_call_id=verify_call.id,
                        name="verify_patient",
                    )
                ],
                "pending_tool_calls": remaining_tool_calls,  # Clear the verification call
                "next_step": "agent" if not remaining_tool_calls else "tools",
            }

        logger.warning(f"Patient verification failed for session {state.session_id}")
        session = session_manager.get_session(state.session_id)
        if session is None:
            return {
                "error": "Session not found",
                "next_step": "error",
            }
        session.increment_failed_attempts()
        updated_info = PatientInfo(
            patient_id=None,
            verified=False,
            failed_attempts=state.patient_info.failed_attempts + 1,
        )

        failure_message = "Unable to verify your identity. Please check your information and try again."

        return {
            "patient_info": updated_info,
            "messages": [
                ToolMessage(
                    content=failure_message,
                    tool_call_id=verify_call.id,
                    name="verify_patient",
                )
            ],
            "pending_tool_calls": remaining_tool_calls,
            "next_step": "agent" if not remaining_tool_calls else "tools",
        }

    except Exception as e:
        logger.error(f"Verification error: {e}", exc_info=True)
        return {
            "messages": [
                ToolMessage(
                    content=f"Verification error: {e}",
                    tool_call_id=verify_call.id,
                    name="verify_patient",
                )
            ],
            "pending_tool_calls": remaining_tool_calls,
            "next_step": "agent" if not remaining_tool_calls else "tools",
        }


def error_handler_node(state: ConversationState) -> dict[str, Any]:
    """Handle errors and implement recovery strategies."""
    logger.error(f"Error handler invoked: {state.error}")

    error = state.error or "Unknown error occurred"

    # Implement different recovery strategies based on error type
    if "rate_limit" in error.lower():
        # Rate limit - add retry with backoff
        retry_message = "I'm experiencing high demand. Let me try again in a moment..."
        return {
            "messages": [AIMessage(content=retry_message)],
            "retry_count": state.retry_count + 1,
            "error": None,
            "next_step": "agent" if state.retry_count < 3 else "end",
        }

    if "token" in error.lower() or "context" in error.lower():
        # Token limit - truncate conversation
        truncate_message = (
            "Our conversation has become quite long. I'll continue with a shortened context to help you better."
        )
        # Keep only last 10 messages and add the notification
        truncated_messages = [*state.messages[-10:], AIMessage(content=truncate_message)]
        return {
            "messages": truncated_messages,
            "error": None,
            "next_step": "agent",
        }

    error_message = "I apologize, but I encountered an error. Please try rephrasing your request."
    return {
        "messages": [AIMessage(content=error_message)],
        "error": None,
        "next_step": "end",
    }


def _get_available_tools() -> list[StructuredTool]:
    """Get tools available based on current state."""
    return get_langgraph_tools()


def _get_tools_map() -> dict[str, StructuredTool]:
    """Get tools as a dictionary for execution."""
    tools = _get_available_tools()
    return {tool.name: tool for tool in tools}
