from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.runtime import ActionLedger


class ActionLedgerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        run_id: UUID,
        action_type: str,
        target_id: str,
        idempotency_key: str,
        status: str,
        request_json: dict[str, Any],
        response_json: dict[str, Any] | None = None,
        error_json: dict[str, Any] | None = None,
    ) -> ActionLedger:
        action = ActionLedger(
            run_id=run_id,
            action_type=action_type,
            target_id=target_id,
            idempotency_key=idempotency_key,
            status=status,
            request_json=request_json,
            response_json=response_json,
            error_json=error_json,
        )
        self.session.add(action)
        self.session.flush()
        self.session.refresh(action)
        return action

    def get_by_id(self, action_id: UUID) -> ActionLedger | None:
        return self.session.get(ActionLedger, action_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> ActionLedger | None:
        statement = select(ActionLedger).where(ActionLedger.idempotency_key == idempotency_key)
        return self.session.scalar(statement)

    def get_replayable_by_idempotency_key(self, idempotency_key: str) -> ActionLedger | None:
        return self.get_by_idempotency_key(idempotency_key)

    def list_for_run(self, run_id: UUID) -> list[ActionLedger]:
        statement = (
            select(ActionLedger)
            .where(ActionLedger.run_id == run_id)
            .order_by(ActionLedger.created_at, ActionLedger.action_id)
        )
        return list(self.session.scalars(statement).all())

    def list_for_run_by_idempotency_key(self, run_id: UUID) -> dict[str, ActionLedger]:
        statement = select(ActionLedger).where(ActionLedger.run_id == run_id)
        return {
            action.idempotency_key: action
            for action in self.session.scalars(statement).all()
        }

    def update_status(
        self,
        action_id: UUID,
        status: str,
        response_json: dict[str, Any] | None = None,
        error_json: dict[str, Any] | None = None,
    ) -> ActionLedger | None:
        action = self.get_by_id(action_id)
        if action is None:
            return None

        action.status = status
        if response_json is not None:
            action.response_json = response_json
        if error_json is not None:
            action.error_json = error_json
        self.session.flush()
        self.session.refresh(action)
        return action
