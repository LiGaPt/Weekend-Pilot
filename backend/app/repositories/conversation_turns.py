from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.runtime import ConversationTurn


class ConversationTurnRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(
        self,
        session_id: UUID,
        run_id: UUID | None,
        speaker_role: str,
        turn_type: str,
        content_text: str,
        payload_json: dict[str, Any],
    ) -> ConversationTurn:
        turn_index = int(
            self.session.scalar(
                select(func.coalesce(func.max(ConversationTurn.turn_index), 0)).where(
                    ConversationTurn.session_id == session_id
                )
            )
            or 0
        ) + 1
        conversation_turn = ConversationTurn(
            session_id=session_id,
            run_id=run_id,
            turn_index=turn_index,
            speaker_role=speaker_role,
            turn_type=turn_type,
            content_text=content_text,
            payload_json=payload_json,
        )
        self.session.add(conversation_turn)
        self.session.flush()
        self.session.refresh(conversation_turn)
        return conversation_turn

    def get_by_id(self, turn_id: UUID) -> ConversationTurn | None:
        return self.session.get(ConversationTurn, turn_id)

    def list_for_session(self, session_id: UUID) -> list[ConversationTurn]:
        statement = (
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
        )
        return list(self.session.scalars(statement).all())

    def list_for_run(self, run_id: UUID) -> list[ConversationTurn]:
        statement = (
            select(ConversationTurn)
            .where(ConversationTurn.run_id == run_id)
            .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
        )
        return list(self.session.scalars(statement).all())
