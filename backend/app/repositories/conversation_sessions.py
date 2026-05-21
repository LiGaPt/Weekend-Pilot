from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.runtime import ConversationSession


class ConversationSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        user_id: UUID,
        channel: str,
        status: str,
        metadata_json: dict[str, Any],
    ) -> ConversationSession:
        conversation_session = ConversationSession(
            user_id=user_id,
            channel=channel,
            status=status,
            metadata_json=metadata_json,
        )
        self.session.add(conversation_session)
        self.session.flush()
        self.session.refresh(conversation_session)
        return conversation_session

    def get_by_id(self, session_id: UUID) -> ConversationSession | None:
        return self.session.get(ConversationSession, session_id)

    def list_for_user(self, user_id: UUID) -> list[ConversationSession]:
        statement = (
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id)
            .order_by(ConversationSession.created_at, ConversationSession.session_id)
        )
        return list(self.session.scalars(statement).all())

    def update_status(self, session_id: UUID, status: str) -> ConversationSession | None:
        conversation_session = self.get_by_id(session_id)
        if conversation_session is None:
            return None

        conversation_session.status = status
        self.session.flush()
        self.session.refresh(conversation_session)
        return conversation_session
