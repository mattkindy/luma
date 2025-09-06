"""Tests for data models."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.conversation import ConversationRequest, ConversationResponse, HealthResponse
from app.models.llm import LLMMessage, TextBlock, ToolResultBlock, ToolUseBlock
from app.models.messages import ConversationMessage
from app.models.patient import Patient
from app.models.session import Session
from app.tools.appointment_actions import AppointmentActionInput
from app.tools.verify_patient import VerifyPatientInput


class TestConversationModels:
    """Tests for conversation request/response models."""

    def test_conversation_request_valid(self):
        """Test valid conversation request."""
        request = ConversationRequest(message="Hello")
        assert request.message == "Hello"
        assert request.session_id is None

    def test_conversation_request_with_session(self):
        """Test conversation request with session ID."""
        request = ConversationRequest(message="Hello", session_id="test-session")
        assert request.message == "Hello"
        assert request.session_id == "test-session"

    def test_conversation_request_from_json(self):
        """Test conversation request parsing from JSON."""
        json_data = '{"message": "Hello, I need help", "session_id": "clhqxrisp0001s67w2qccjhqr"}'
        data = json.loads(json_data)
        request = ConversationRequest.model_validate(data)
        assert request.message == "Hello, I need help"
        assert request.session_id == "clhqxrisp0001s67w2qccjhqr"

    def test_conversation_request_from_json_no_session(self):
        """Test conversation request parsing from JSON without session."""
        json_data = '{"message": "Hello"}'
        data = json.loads(json_data)
        request = ConversationRequest.model_validate(data)
        assert request.message == "Hello"
        assert request.session_id is None

    def test_conversation_response_valid(self):
        """Test valid conversation response."""
        response = ConversationResponse(response="Hi there!", session_id="test-session")
        assert response.response == "Hi there!"
        assert response.session_id == "test-session"

    def test_health_response_valid(self):
        """Test valid health response."""
        now = datetime.now(UTC)
        response = HealthResponse(status="healthy", timestamp=now, version="1.0.0")
        assert response.status == "healthy"
        assert response.timestamp == now
        assert response.version == "1.0.0"


class TestSessionModels:
    """Tests for session and message models."""

    def test_conversation_message_valid(self):
        """Test valid conversation message."""
        now = datetime.now(UTC)
        message = ConversationMessage(role="user", content="Hello", timestamp=now)
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.timestamp == now
        assert message.tool_calls is None

    def test_conversation_message_with_tools(self):
        """Test conversation message with tool calls."""
        now = datetime.now(UTC)
        tool_calls = [{"name": "test_tool", "input": {}}]
        message = ConversationMessage(role="assistant", content="Using tools...", timestamp=now, tool_calls=tool_calls)
        assert message.tool_calls == tool_calls

    def test_conversation_message_invalid_role(self):
        """Test conversation message with invalid role."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationMessage(
                role="invalid",  # type: ignore
                content="Hello",
                timestamp=datetime.now(UTC),
            )
        assert "Input should be 'user', 'assistant' or 'system'" in str(exc_info.value)


class TestPatientModels:
    """Tests for patient models."""

    def test_patient_valid(self):
        """Test valid patient model."""
        patient = Patient(id="PATIENT_001", name="John Smith", phone="555-123-4567", date_of_birth="1980-01-01")
        assert patient.id == "PATIENT_001"
        assert patient.name == "John Smith"
        assert patient.phone == "555-123-4567"
        assert patient.date_of_birth == "1980-01-01"


class TestLLMModels:
    """Tests for LLM-related models."""

    def test_llm_message_text_content(self):
        """Test LLM message with text content."""
        message = LLMMessage(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"

    def test_llm_message_content_blocks(self):
        """Test LLM message with content blocks."""
        blocks = [TextBlock(text="Hello")]
        message = LLMMessage(role="assistant", content=blocks)
        assert message.role == "assistant"
        assert len(message.content) == 1
        assert message.content[0].text == "Hello"

    def test_text_block_valid(self):
        """Test valid text block."""
        block = TextBlock(text="Hello world")
        assert block.type == "text"
        assert block.text == "Hello world"

    def test_tool_use_block_valid(self):
        """Test valid tool use block."""
        block = ToolUseBlock(id="tool_001", name="test_tool", input={"param": "value"})
        assert block.type == "tool_use"
        assert block.id == "tool_001"
        assert block.name == "test_tool"
        assert block.input == {"param": "value"}

    def test_tool_result_block_valid(self):
        """Test valid tool result block."""
        block = ToolResultBlock(tool_use_id="tool_001", content="Success")
        assert block.type == "tool_result"
        assert block.tool_use_id == "tool_001"
        assert block.content == "Success"
        assert block.is_error is False

    def test_tool_result_block_error(self):
        """Test tool result block with error."""
        block = ToolResultBlock(tool_use_id="tool_001", content="Error occurred", is_error=True)
        assert block.is_error is True

    def test_content_blocks_from_anthropic_json(self):
        """Test parsing actual Anthropic content blocks from JSON."""
        # Real Anthropic response format (from your example)
        anthropic_content = [
            {
                "citations": None,
                "text": (
                    "I'll help you verify your identity before we can proceed with any appointment-related actions."
                ),
                "type": "text",
            },
            {
                "id": "toolu_011NMUEGn7XedTwffFDdTphg",
                "input": {"name": "Matt Kindy", "date_of_birth": "2000-01-23", "phone": "832-516-4322"},
                "name": "verify_patient",
                "type": "tool_use",
            },
        ]

        # Test TextBlock parsing
        text_block = TextBlock.model_validate(anthropic_content[0])
        assert text_block.type == "text"
        assert "verify your identity" in text_block.text
        # Note: citations field is ignored due to Config.extra = "ignore"

        # Test ToolUseBlock parsing
        tool_block = ToolUseBlock.model_validate(anthropic_content[1])
        assert tool_block.type == "tool_use"
        assert tool_block.id == "toolu_011NMUEGn7XedTwffFDdTphg"
        assert tool_block.name == "verify_patient"
        assert tool_block.input["name"] == "Matt Kindy"
        assert tool_block.input["phone"] == "832-516-4322"


class TestToolInputModels:
    """Tests for tool input validation models."""

    def test_verify_patient_input_valid(self):
        """Test valid patient verification input."""
        input_data = VerifyPatientInput(name="John Smith", phone="555-123-4567", date_of_birth="1980-01-01")
        assert input_data.name == "John Smith"
        assert input_data.phone == "555-123-4567"
        assert input_data.date_of_birth == "1980-01-01"

    def test_verify_patient_input_from_json(self):
        """Test patient verification input from JSON (like tool calls)."""
        # Simulate JSON from Anthropic tool call
        json_data = {"name": "Matt Kindy", "date_of_birth": "2000-01-23", "phone": "832-516-4322"}

        input_data = VerifyPatientInput.model_validate(json_data)
        assert input_data.name == "Matt Kindy"
        assert input_data.date_of_birth == "2000-01-23"
        assert input_data.phone == "832-516-4322"

    def test_verify_patient_input_from_json_string(self):
        """Test patient verification input from JSON string."""
        json_string = '{"name": "Jane Doe", "phone": "555-987-6543", "date_of_birth": "1985-05-15"}'
        data = json.loads(json_string)
        input_data = VerifyPatientInput.model_validate(data)
        assert input_data.name == "Jane Doe"
        assert input_data.phone == "555-987-6543"
        assert input_data.date_of_birth == "1985-05-15"

    def test_verify_patient_input_name_validation(self):
        """Test name validation in patient verification."""
        # Valid names (must have first and last name)
        valid_names = ["John Smith", "Mary Jane Johnson", "Patrick O'Connor", "Jean-Luc Picard"]
        for name in valid_names:
            input_data = VerifyPatientInput(name=name, phone="555-123-4567", date_of_birth="1980-01-01")
            assert input_data.name  # Should not raise

        # Invalid names
        with pytest.raises(ValidationError):
            VerifyPatientInput(
                name="John",  # Missing last name
                phone="555-123-4567",
                date_of_birth="1980-01-01",
            )

        with pytest.raises(ValidationError):
            VerifyPatientInput(
                name="John123",  # Contains numbers
                phone="555-123-4567",
                date_of_birth="1980-01-01",
            )

    def test_verify_patient_input_phone_validation(self):
        """Test phone validation in patient verification."""
        # Valid phone format
        input_data = VerifyPatientInput(name="John Smith", phone="555-123-4567", date_of_birth="1980-01-01")
        assert input_data.phone == "555-123-4567"

        # Invalid phone formats
        invalid_phones = [
            "555.123.4567",  # Dots instead of dashes
            "(555) 123-4567",  # Parentheses
            "5551234567",  # No separators
            "555-123-456",  # Too short
            "555-123-45678",  # Too long
        ]

        for phone in invalid_phones:
            with pytest.raises(ValidationError):
                VerifyPatientInput(name="John Smith", phone=phone, date_of_birth="1980-01-01")

    def test_verify_patient_input_date_validation(self):
        """Test date of birth validation."""
        # Valid date
        input_data = VerifyPatientInput(name="John Smith", phone="555-123-4567", date_of_birth="1980-01-01")
        assert input_data.date_of_birth == "1980-01-01"

        # Invalid date formats
        invalid_dates = [
            "01/01/1980",  # MM/DD/YYYY format
            "1980-1-1",  # Single digit month/day
            "80-01-01",  # Two digit year
            "1980/01/01",  # Slashes instead of dashes
        ]

        for date in invalid_dates:
            with pytest.raises(ValidationError):
                VerifyPatientInput(name="John Smith", phone="555-123-4567", date_of_birth=date)

        # Future date
        with pytest.raises(ValidationError):
            VerifyPatientInput(name="John Smith", phone="555-123-4567", date_of_birth="2030-01-01")

        # Too old
        with pytest.raises(ValidationError):
            VerifyPatientInput(name="John Smith", phone="555-123-4567", date_of_birth="1800-01-01")

    def test_appointment_action_input_valid(self):
        """Test valid appointment action input."""
        input_data = AppointmentActionInput(appointment_id="APT_001")
        assert input_data.appointment_id == "APT_001"

    def test_appointment_action_input_from_json(self):
        """Test appointment action input from JSON."""
        # Simulate JSON from Anthropic tool call
        json_data = {"appointment_id": "APT_123"}
        input_data = AppointmentActionInput.model_validate(json_data)
        assert input_data.appointment_id == "APT_123"

    def test_appointment_action_input_from_json_string(self):
        """Test appointment action input from JSON string."""
        json_string = '{"appointment_id": "APT_456"}'
        data = json.loads(json_string)
        input_data = AppointmentActionInput.model_validate(data)
        assert input_data.appointment_id == "APT_456"

    def test_appointment_action_input_validation(self):
        """Test appointment ID validation."""
        # Valid IDs
        valid_ids = ["APT_001", "APT_123", "APT_999"]
        for apt_id in valid_ids:
            input_data = AppointmentActionInput(appointment_id=apt_id)
            assert input_data.appointment_id == apt_id

        # Invalid IDs
        invalid_ids = [
            "apt_001",  # Lowercase
            "APT_1",  # Too short
            "APT_1234",  # Too long
            "APPT_001",  # Wrong prefix
            "APT-001",  # Wrong separator
        ]

        for apt_id in invalid_ids:
            with pytest.raises(ValidationError):
                AppointmentActionInput(appointment_id=apt_id)


class TestSessionModel:
    """Tests for session model (dataclass)."""

    def test_session_creation(self):
        """Test session creation with defaults."""
        session = Session(session_id="test_session")
        assert session.session_id == "test_session"
        assert session.patient_id is None
        assert session.verified is False
        assert session.failed_verification_attempts == 0
        assert len(session.conversation_history) == 0

    def test_session_set_verified(self):
        """Test setting session as verified."""
        session = Session(session_id="test_session")

        session.set_verified("PATIENT_001")
        assert session.verified is True
        assert session.patient_id == "PATIENT_001"

    def test_session_increment_failed_attempts(self):
        """Test incrementing failed verification attempts."""
        session = Session(session_id="test_session")

        session.increment_failed_attempts()
        assert session.failed_verification_attempts == 1

        session.increment_failed_attempts()
        assert session.failed_verification_attempts == 2
