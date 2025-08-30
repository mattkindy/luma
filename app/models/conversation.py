"""Conversation and session data models."""

from datetime import datetime

from pydantic import BaseModel


class ConversationRequest(BaseModel):
    """Request model for conversation endpoint."""

    message: str
    session_id: str | None = None


class ConversationResponse(BaseModel):
    """Response model for conversation endpoint."""

    response: str
    session_id: str


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str
    timestamp: datetime
    version: str
