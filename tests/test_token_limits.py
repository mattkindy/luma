"""Tests for token validation and truncation functionality."""

from unittest.mock import Mock, patch

import pytest

from app.clients.anthropic import AnthropicClient, AnthropicConfig, AnthropicMessage
from app.models.session import Session
from app.services.conversation import ConversationService


class TestTokenValidation:
    """Tests for message token validation."""

    @pytest.fixture
    def anthropic_client(self):
        """Create AnthropicClient for testing."""
        config = AnthropicConfig(max_message_tokens=1000)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            client = AnthropicClient(config=config)
            # Mock tokenizer for consistent testing
            client.tokenizer = Mock()
            return client

    def test_validate_message_tokens_within_limit(self, anthropic_client):
        """Test that messages within token limit pass validation."""
        # Mock tokenizer to return token count under limit
        anthropic_client.tokenizer.encode.return_value = ["token"] * 500

        # Should not raise exception
        anthropic_client.validate_message_tokens("Short message")

    def test_validate_message_tokens_exceeds_limit(self, anthropic_client):
        """Test that messages exceeding token limit raise ValueError."""
        # Mock tokenizer to return token count over limit
        anthropic_client.tokenizer.encode.return_value = ["token"] * 1500

        with pytest.raises(ValueError, match="Message exceeds token limit"):
            anthropic_client.validate_message_tokens("Very long message")

    def test_validate_message_tokens_fallback_without_tokenizer(self, anthropic_client):
        """Test token validation fallback when tokenizer is unavailable."""
        anthropic_client.tokenizer = None

        # Short message (under 4000 chars = ~1000 tokens) should pass
        short_message = "a" * 3000
        anthropic_client.validate_message_tokens(short_message)

        # Long message (over 4000 chars = ~1000 tokens) should fail
        long_message = "a" * 5000
        with pytest.raises(ValueError, match="Message exceeds token limit"):
            anthropic_client.validate_message_tokens(long_message)


class TestConversationTruncation:
    """Tests for conversation truncation functionality."""

    @pytest.fixture
    def anthropic_client(self):
        """Create AnthropicClient for testing."""
        config = AnthropicConfig(max_conversation_tokens=10000, token_headroom=1000, max_message_tokens=1000)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            client = AnthropicClient(config=config)
            # Mock tokenizer for consistent testing
            client.tokenizer = Mock()
            return client

    def test_truncate_conversation_within_limit(self, anthropic_client):
        """Test that conversations within limits are not truncated."""
        # Mock tokenizer to return reasonable token counts
        anthropic_client.tokenizer.encode.return_value = ["token"] * 100

        messages = [
            AnthropicMessage(role="user", content="Message 1"),
            AnthropicMessage(role="assistant", content="Response 1"),
            AnthropicMessage(role="user", content="Message 2"),
        ]

        result = anthropic_client.truncate_conversation(messages, "System prompt")

        # All messages should be preserved
        assert len(result) == 3
        assert result == messages

    def test_truncate_conversation_exceeds_limit(self, anthropic_client):
        """Test that conversations exceeding limits are truncated from beginning."""

        # Mock tokenizer to return high token counts for truncation
        def mock_encode(text):
            if "System prompt" in text:
                return ["token"] * 500  # System prompt tokens
            return ["token"] * 3000  # High token count per message

        anthropic_client.tokenizer.encode.side_effect = mock_encode

        messages = [
            AnthropicMessage(role="user", content="Message 1"),
            AnthropicMessage(role="assistant", content="Response 1"),
            AnthropicMessage(role="user", content="Message 2"),
            AnthropicMessage(role="assistant", content="Response 2"),
            AnthropicMessage(role="user", content="Message 3"),
        ]

        result = anthropic_client.truncate_conversation(messages, "System prompt")

        # Should truncate from beginning, keeping most recent messages
        assert len(result) < len(messages)
        # Should preserve the most recent messages
        assert result[-1].content == "Message 3"

    def test_truncate_conversation_empty_messages(self, anthropic_client):
        """Test truncation with empty message list."""
        result = anthropic_client.truncate_conversation([], "System prompt")
        assert result == []


class TestConversationServiceValidation:
    """Tests for conversation service message validation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session for testing."""
        return Session(session_id="test-session")

    @pytest.fixture
    def conversation_service(self):
        """Create ConversationService with mocked dependencies."""
        with patch("app.services.conversation.get_anthropic_client") as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            mock_llm_service = Mock()
            mock_tools_registry = Mock()

            service = ConversationService(mock_llm_service, mock_tools_registry)
            return service, mock_client

    @pytest.mark.asyncio
    async def test_process_message_validates_tokens(self, conversation_service, mock_session):
        """Test that process_message validates message tokens."""
        service, mock_client = conversation_service

        # Mock validation to raise ValueError
        mock_client.validate_message_tokens.side_effect = ValueError("Token limit exceeded")

        with pytest.raises(ValueError, match="Your message is too long"):
            await service.process_message("Long message", mock_session)

        # Verify validation was called
        mock_client.validate_message_tokens.assert_called_once_with("Long message")

    @pytest.mark.asyncio
    async def test_process_message_valid_tokens_proceeds(self, conversation_service, mock_session):
        """Test that valid messages proceed to processing."""
        service, mock_client = conversation_service

        # Mock validation to pass
        mock_client.validate_message_tokens.return_value = None

        # Mock the LLM service to return a response
        mock_result = Mock()
        mock_result.content = [Mock(type="text", text="AI response")]
        mock_result.turns = 1
        mock_result.stop_reason = "complete"

        # Make execute_agent_loop async
        async def mock_execute_agent_loop(*args, **kwargs):
            return await mock_result

        service.llm_service.execute_agent_loop = mock_execute_agent_loop

        # Mock tools registry
        service.tools_registry.get_llm_tools.return_value = {}

        result = await service.process_message("Valid message", mock_session)

        # Should process successfully
        assert result == "AI response"
        mock_client.validate_message_tokens.assert_called_once_with("Valid message")


if __name__ == "__main__":
    pytest.main([__file__])
