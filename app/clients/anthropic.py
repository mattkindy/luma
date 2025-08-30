"""Anthropic API client with rate limiting and error handling."""

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import tiktoken
from anthropic import Anthropic, APIError
from anthropic.types import ContentBlock as AnthropicContentBlock
from anthropic.types import Message
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from pydantic import BaseModel

from app.models.llm import ContentBlock
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CacheControl(BaseModel):
    """Cache control configuration for prompt caching."""

    type: Literal["ephemeral"] = "ephemeral"
    ttl: Literal["5m", "1h"] = "5m"


class AnthropicMessage(BaseModel):
    """Message format for Anthropic API."""

    role: Literal["user", "assistant", "system"]
    content: str | list[ContentBlock]


class AnthropicTool(BaseModel):
    """Tool definition for Anthropic API."""

    name: str
    description: str
    input_schema: dict[str, Any]
    cache_control: CacheControl | None = None


@dataclass
class TokenUsage:
    """Token usage information from Anthropic API."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class AnthropicResponse:
    """Structured response from Anthropic API."""

    content: list[ContentBlock]
    stop_reason: str | None
    usage: TokenUsage
    model: str


@dataclass
class AnthropicConfig:
    """Configuration for Anthropic API client."""

    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 1000
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0

    # Token limits for validation and truncation
    max_message_tokens: int = 2000  # Maximum tokens per individual message
    max_conversation_tokens: int = 200000  # Claude 4 Sonnet default context window
    token_headroom: int = 2000  # Reserve tokens for response


class AnthropicRateLimiter:
    """Professional rate limiter using the limits library."""

    def __init__(self, requests_per_minute: int = 50, tokens_per_minute: int = 40_000):
        """Initialize rate limiter with proper rate limiting library.

        Args:
            requests_per_minute: Maximum requests per minute
            tokens_per_minute: Maximum tokens per minute
        """
        self.storage = MemoryStorage()
        self.limiter = MovingWindowRateLimiter(self.storage)

        self.request_limit = parse(f"{requests_per_minute}/minute")
        self.token_limit = parse(f"{tokens_per_minute}/minute")

    async def check_rate_limit(self, estimated_tokens: int, identifier: str = "anthropic") -> None:
        """Check if request is within rate limits."""
        logger.debug(f"Checking rate limit for {estimated_tokens} tokens, identifier: {identifier}")

        # Check request rate limit
        if not self.limiter.hit(self.request_limit, identifier):
            # Rate limit exceeded, calculate wait time
            window_stats = self.limiter.get_window_stats(self.request_limit, identifier)
            if window_stats:
                reset_time = window_stats.reset_time
                wait_time = max(0, reset_time - asyncio.get_event_loop().time())
                if wait_time > 0:
                    logger.warning(f"Request rate limit exceeded, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)

        token_identifier = f"{identifier}_tokens"
        if not self.limiter.hit(self.token_limit, token_identifier, cost=estimated_tokens):
            # Token rate limit exceeded
            window_stats = self.limiter.get_window_stats(self.token_limit, token_identifier)
            if window_stats:
                reset_time = window_stats.reset_time
                wait_time = max(0, reset_time - asyncio.get_event_loop().time())
                if wait_time > 0:
                    logger.warning(f"Token rate limit exceeded, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)


class AnthropicClient:
    """Low-level Anthropic API client with rate limiting and error handling."""

    tokenizer: tiktoken.Encoding | None = None
    api_key: str
    client: Anthropic
    config: AnthropicConfig
    rate_limiter: AnthropicRateLimiter = AnthropicRateLimiter()

    def __init__(self, api_key: str | None = None, config: AnthropicConfig | None = None):
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            config: Client configuration
        """
        anthropic_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.api_key = anthropic_api_key

        self.client = Anthropic(api_key=self.api_key)
        self.config = config or AnthropicConfig()

        # Initialize tokenizer for token estimation
        try:
            # Close approximation for Claude
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            self.tokenizer = None

    async def create_message(
        self,
        messages: list[AnthropicMessage],
        system_prompt: str,
        tools: list[AnthropicTool] | None = None,
        **kwargs,
    ) -> AnthropicResponse:
        """Create a message with Claude API.

        Args:
            messages: Conversation history
            system_prompt: System prompt for Claude
            tools: Available tools for Claude
            **kwargs: Additional parameters for Claude API

        Returns:
            Structured Anthropic response
        """
        truncated_messages = self.truncate_conversation(messages, system_prompt, tools)

        # Estimate tokens for rate limiting
        estimated_tokens = self._estimate_tokens(truncated_messages, system_prompt)
        logger.debug(f"Estimated tokens: {estimated_tokens}")
        await self.rate_limiter.check_rate_limit(estimated_tokens)

        message_dicts = [msg.model_dump() for msg in truncated_messages]
        tool_dicts = [tool.model_dump() for tool in tools] if tools else None

        logger.debug(f"Creating message with {len(truncated_messages)} messages, {len(tools) if tools else 0} tools")

        request_params = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "system": system_prompt,
            "messages": message_dicts,
            "tools": tool_dicts,
        }

        logger.debug(f"Making Anthropic API call with model: {request_params['model']}")
        response: Message = await self._request_with_retries(lambda: self.client.messages.create(**request_params))

        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                cache_creation_input_tokens=response.usage.cache_creation_input_tokens or 0,
                cache_read_input_tokens=response.usage.cache_read_input_tokens or 0,
            )

        logger.debug(
            f"Response received - Stop reason: {response.stop_reason}, Content blocks: {len(response.content)}"
        )

        return AnthropicResponse(
            content=self._convert_content_blocks(response.content),
            stop_reason=response.stop_reason,
            usage=usage,
            model=response.model,
        )

    async def _request_with_retries[T](self, call: Callable[[], T]) -> T:
        """Execute Anthropic API request with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                return call()

            except APIError as e:
                if hasattr(e, "status_code") and e.status_code == 429:  # Rate limit exceeded
                    retry_after = 60
                    if hasattr(e, "response") and e.response and hasattr(e.response, "headers"):
                        retry_after = int(e.response.headers.get("retry-after", 60))

                    if retry_after < 120 and attempt < self.config.max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue

                elif hasattr(e, "status_code") and e.status_code >= 500 and attempt < self.config.max_retries - 1:
                    # Server error, retry with exponential backoff
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    continue

                # Re-raise if not retryable or max retries reached
                raise

            except Exception:
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    continue
                raise

        raise Exception(f"Failed to complete request after {self.config.max_retries} attempts")

    def _convert_content_blocks(self, anthropic_content: list[AnthropicContentBlock]) -> list[ContentBlock]:
        """Convert Anthropic content blocks to our ContentBlock types."""
        from app.models.llm import TextBlock, ToolUseBlock

        converted_blocks: list[ContentBlock] = []
        for block in anthropic_content:
            try:
                # Convert Anthropic content block to dict then to our models
                if hasattr(block, "model_dump"):
                    block_dict = block.model_dump()
                elif hasattr(block, "__dict__"):
                    block_dict = block.__dict__
                else:
                    block_dict = dict(block)

                if block_dict.get("type") == "text":
                    converted_blocks.append(TextBlock.model_validate(block_dict))
                elif block_dict.get("type") == "tool_use":
                    converted_blocks.append(ToolUseBlock.model_validate(block_dict))
                else:
                    logger.warning(f"Unknown content block type: {block_dict.get('type')}")

            except Exception as e:
                logger.error(f"Failed to convert content block: {e}, block: {block}")
                # Skip malformed blocks rather than failing the entire response
                continue

        return converted_blocks

    def _estimate_tokens(self, messages: list[AnthropicMessage], system_prompt: str) -> int:
        """Estimate token count for rate limiting.

        Args:
            messages: Conversation messages
            system_prompt: System prompt

        Returns:
            Estimated token count
        """
        # Combine all text content
        text_content = system_prompt

        for message in messages:
            if isinstance(message.content, str):
                text_content += message.content
            elif isinstance(message.content, list):
                for item in message.content:
                    if isinstance(item, dict) and "text" in item:
                        text_content += item["text"]

        # Estimate tokens (rough approximation)
        try:
            return len(self.tokenizer.encode(text_content)) if self.tokenizer else len(text_content) // 4
        except Exception:
            # Fallback: roughly 4 characters per token
            return len(text_content) // 4

    def estimate_message_tokens(self, message: str) -> int:
        """Estimate token count for a single message.

        Args:
            message: Message content

        Returns:
            Estimated token count
        """
        try:
            return len(self.tokenizer.encode(message)) if self.tokenizer else len(message) // 4
        except Exception:
            # Fallback: roughly 4 characters per token
            return len(message) // 4

    def validate_message_tokens(self, message: str) -> None:
        """Validate that a message doesn't exceed token limits.

        Args:
            message: Message content

        Raises:
            ValueError: If message exceeds token limit
        """
        token_count = self.estimate_message_tokens(message)
        if token_count > self.config.max_message_tokens:
            raise ValueError(
                f"Message exceeds token limit: {token_count} tokens > {self.config.max_message_tokens} limit"
            )

    def truncate_conversation(
        self, messages: list[AnthropicMessage], system_prompt: str, tools: list[AnthropicTool] | None = None
    ) -> list[AnthropicMessage]:
        """Truncate conversation from the beginning to fit within token limits.

        Args:
            messages: Conversation messages
            system_prompt: System prompt
            tools: Available tools

        Returns:
            Truncated message list that fits within limits
        """
        if not messages:
            return messages

        available_tokens = self.config.max_conversation_tokens - self.config.token_headroom

        system_tokens = self.estimate_message_tokens(system_prompt)

        tool_tokens = 0
        if tools:
            tool_content = ""
            for tool in tools:
                tool_content += tool.name + tool.description + str(tool.input_schema)
            tool_tokens = self.estimate_message_tokens(tool_content)

        available_tokens -= system_tokens + tool_tokens

        truncated_messages: list[AnthropicMessage] = []
        current_tokens = 0

        for message in reversed(messages):
            message_tokens = 0
            if isinstance(message.content, str):
                message_tokens = self.estimate_message_tokens(message.content)
            elif isinstance(message.content, list):
                content_text = ""
                for item in message.content:
                    if isinstance(item, dict) and "text" in item:
                        content_text += item["text"]
                message_tokens = self.estimate_message_tokens(content_text)

            if current_tokens + message_tokens <= available_tokens:
                truncated_messages.insert(0, message)
                current_tokens += message_tokens
            else:
                # Stop adding messages if we exceed the limit
                break

        if len(truncated_messages) < len(messages):
            logger.warning(
                f"Truncated conversation from {len(messages)} to {len(truncated_messages)} messages "
                f"to fit within {available_tokens} token limit"
            )

        return truncated_messages


_anthropic_client: AnthropicClient | None = None


def get_anthropic_client() -> AnthropicClient:
    """Get or create Anthropic client instance."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AnthropicClient()
    return _anthropic_client
