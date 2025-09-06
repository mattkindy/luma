"""Session management for in-memory storage."""

from datetime import UTC, datetime, timedelta

from cuid2 import cuid_wrapper

from app.models.session import Session

cuid = cuid_wrapper()


class InMemorySessionManager:
    """In-memory session manager for Phase 1 development."""

    def __init__(self, session_timeout_minutes: int = 60):
        """Initialize session manager.

        Args:
            session_timeout_minutes: Minutes before session expires
        """
        self.sessions: dict[str, Session] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)

    def get_or_create_session(self, session_id: str | None = None) -> Session:
        """Get existing session or create new one.

        Args:
            session_id: Optional existing session ID

        Returns:
            Session object (existing or newly created)
        """
        self._cleanup_expired_sessions()

        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.update_activity()
            return session

        new_session_id = session_id or self._generate_session_id()
        session = Session(session_id=new_session_id)
        self.sessions[new_session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get existing session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found and not expired, None otherwise
        """
        self._cleanup_expired_sessions()

        session = self.sessions.get(session_id)
        if session:
            session.update_activity()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def _generate_session_id(self) -> str:
        """Generate a new CUID-based session ID."""
        return cuid()

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from memory."""
        current_time = datetime.now(UTC)
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.sessions[session_id]

    def get_session_count(self) -> int:
        """Get current number of active sessions."""
        self._cleanup_expired_sessions()
        return len(self.sessions)

    def get_verified_session_count(self) -> int:
        """Get current number of verified sessions."""
        self._cleanup_expired_sessions()
        return sum(1 for session in self.sessions.values() if session.verified)


session_manager = InMemorySessionManager()
