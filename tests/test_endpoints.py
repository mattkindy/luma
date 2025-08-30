"""Tests for API endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check_returns_200(self):
        """Test that health check returns 200 status."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self):
        """Test that health check returns expected JSON structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data

        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_health_check_content_type(self):
        """Test that health check returns JSON content type."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


class TestConversationEndpoint:
    """Tests for the conversation endpoint."""

    def test_conversation_returns_200(self):
        """Test that conversation endpoint returns 200 status."""
        response = client.post("/conversation", json={"message": "Hello"})
        assert response.status_code == 200

    def test_conversation_response_structure(self):
        """Test that conversation endpoint returns expected JSON structure."""
        response = client.post("/conversation", json={"message": "Hello"})
        data = response.json()

        assert "response" in data
        assert "session_id" in data

        assert isinstance(data["response"], str)
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0

    def test_conversation_with_session_id(self):
        """Test that conversation endpoint uses provided session ID."""
        response = client.post("/conversation", json={"message": "Hello"})
        data = response.json()
        test_session_id = data["session_id"]
        response = client.post("/conversation", json={"message": "Hello", "session_id": test_session_id})
        data = response.json()

        print(f"Conversation response: {data}")

        assert data["session_id"] == test_session_id

    def test_conversation_generates_session_id(self):
        """Test that conversation endpoint generates session ID when not provided."""
        response = client.post("/conversation", json={"message": "Hello"})
        data = response.json()

        # Session ID should be a CUID (24 characters, starts with lowercase letter)
        assert len(data["session_id"]) == 24
        assert data["session_id"][0].islower()
        assert data["session_id"].isalnum()

    def test_conversation_missing_message(self):
        """Test that conversation endpoint requires message field."""
        response = client.post("/conversation", json={})
        assert response.status_code == 422  # Validation error

    def test_conversation_empty_message(self):
        """Test that conversation endpoint handles empty message."""
        response = client.post("/conversation", json={"message": ""})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data

    def test_conversation_content_type(self):
        """Test that conversation endpoint returns JSON content type."""
        response = client.post("/conversation", json={"message": "Hello"})
        assert response.headers["content-type"] == "application/json"


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_json_available(self):
        """Test that OpenAPI JSON specification is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_swagger_ui_available(self):
        """Test that Swagger UI is available."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_available(self):
        """Test that ReDoc is available."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
