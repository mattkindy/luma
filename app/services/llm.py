"""LLM service for high-level AI operations like agent loops."""

from app.clients.anthropic import (
    AnthropicClient,
    AnthropicMessage,
    AnthropicResponse,
    AnthropicTool,
    get_anthropic_client,
)
from app.models.llm import (
    AgentLoopResult,
    ContentBlock,
    LLMMessage,
    LLMResponse,
    LLMTool,
    LLMUsage,
    TextBlock,
    ToolResultBlock,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """High-level LLM service for agent operations and conversation management."""

    def __init__(self, client: AnthropicClient | None = None):
        """Initialize LLM service.

        Args:
            client: Anthropic client (defaults to global instance)
        """
        self.client = client or get_anthropic_client()

    def _convert_anthropic_response(self, anthropic_response: AnthropicResponse) -> LLMResponse:
        """Convert Anthropic response to provider-agnostic LLM response."""
        usage = None
        if anthropic_response.usage:
            usage = LLMUsage(
                input_tokens=anthropic_response.usage.input_tokens,
                output_tokens=anthropic_response.usage.output_tokens,
                total_tokens=anthropic_response.usage.total_tokens,
            )

        return LLMResponse(
            content=anthropic_response.content,
            stop_reason=anthropic_response.stop_reason,
            usage=usage,
            model=anthropic_response.model,
            provider="anthropic",
        )

    async def execute_agent_loop(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        tools: dict[str, LLMTool],
        max_turns: int = 10,
        **kwargs,
    ) -> AgentLoopResult:
        """Execute an agent loop with tool calling until completion.

        Args:
            messages: Initial conversation messages
            system_prompt: System prompt for Claude
            tools: Dictionary of available tools with schemas and callables
            max_turns: Maximum number of turns to prevent infinite loops
            **kwargs: Additional parameters for Claude API

        Returns:
            Structured result with conversation history and metadata
        """
        logger.info(
            f"Starting agent loop with {len(messages)} initial messages, {len(tools)} tools, max_turns: {max_turns}"
        )
        current_messages = messages.copy()
        turns = 0

        usage = LLMUsage()

        while turns < max_turns:
            turns += 1
            logger.debug(f"Agent loop turn {turns}/{max_turns}")

            anthropic_messages = [AnthropicMessage(role=msg.role, content=msg.content) for msg in current_messages]

            # Create tools with cache control on the last tool for prompt caching
            tool_list = list(tools.values())
            anthropic_tools = []

            for i, tool in enumerate(tool_list):
                # Add cache control to the last tool to cache all tool definitions
                cache_control = None
                if i == len(tool_list) - 1:  # Last tool
                    from app.clients.anthropic import CacheControl

                    cache_control = CacheControl(type="ephemeral", ttl="5m")

                anthropic_tools.append(
                    AnthropicTool(
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.input_schema,
                        cache_control=cache_control,
                    )
                )

            logger.debug(f"Calling LLM with {len(anthropic_messages)} messages and {len(anthropic_tools)} tools")
            response = await self.client.create_message(
                messages=anthropic_messages,
                system_prompt=system_prompt,
                tools=anthropic_tools,
                **kwargs,
            )

            usage.input_tokens += response.usage.input_tokens
            usage.output_tokens += response.usage.output_tokens
            usage.total_tokens += response.usage.total_tokens
            usage.cache_creation_input_tokens += response.usage.cache_creation_input_tokens
            usage.cache_read_input_tokens += response.usage.cache_read_input_tokens

            logger.debug(f"LLM response - Stop reason: {response.stop_reason}. ")

            if response.stop_reason == "tool_use":
                tool_use_blocks = [
                    block for block in response.content if hasattr(block, "type") and block.type == "tool_use"
                ]
                logger.info(f"LLM wants to use {len(tool_use_blocks)} tools")

                if tool_use_blocks:
                    current_messages.append(LLMMessage(role="assistant", content=response.content))

                    tool_results: list[ContentBlock] = []
                    for tool_block in tool_use_blocks:
                        tool_name = tool_block.name
                        tool_input = tool_block.input
                        logger.debug(f"Executing tool: {tool_name} with input: {tool_input}")

                        if tool_name in tools:
                            try:
                                result = await tools[tool_name].callable(tool_input)
                                logger.debug(f"Tool {tool_name} succeeded: {str(result)[:100]}...")
                                tool_results.append(
                                    ToolResultBlock(
                                        tool_use_id=tool_block.id,
                                        content=str(result),
                                        is_error=False,
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Tool {tool_name} failed: {e}")
                                tool_results.append(
                                    ToolResultBlock(
                                        tool_use_id=tool_block.id,
                                        content=f"Error: {e!s}",
                                        is_error=True,
                                    )
                                )
                        else:
                            logger.error(f"Unknown tool requested: {tool_name}")
                            tool_results.append(
                                ToolResultBlock(
                                    tool_use_id=tool_block.id,
                                    content=f"Error: Unknown tool {tool_name}",
                                    is_error=True,
                                )
                            )

                    current_messages.append(LLMMessage(role="user", content=tool_results))

                    continue

            # No tool use, conversation is complete
            logger.info(f"Agent loop completed successfully in {turns} turns")
            return AgentLoopResult(
                content=response.content,
                stop_reason=response.stop_reason,
                messages=current_messages,
                turns=turns,
                usage=usage,
            )

        # Max turns reached
        logger.warning(f"Agent loop reached max turns ({max_turns})")
        return AgentLoopResult(
            content=[
                TextBlock(
                    type="text",
                    text=(
                        "I apologize, but our conversation has reached the maximum number of turns. "
                        "Please start a new conversation."
                    ),
                )
            ],
            stop_reason="max_turns",
            messages=current_messages,
            turns=turns,
            usage=usage,
        )


_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
