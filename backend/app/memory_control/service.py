from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.memory_control.schemas import (
    MemoryControlEvent,
    MemoryControlItemSummary,
    MemoryControlListResponse,
    MemoryControlMutationResponse,
    MemoryUserControlAction,
)
from backend.app.memory_lifecycle import resolve_memory_lifecycle_state
from backend.app.repositories import MemoryItemRepository


_ACTION_TARGET_STATUS: dict[MemoryUserControlAction, str] = {
    "disable": "disabled",
    "suppress": "ignored",
}


class MemoryUserControlServiceError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class MemoryUserControlService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = MemoryItemRepository(session)

    def list_items(self, user_id: UUID) -> MemoryControlListResponse:
        rows = self.repository.list_for_user(user_id)
        return MemoryControlListResponse(
            user_id=user_id,
            items=[self._serialize_item(row) for row in rows],
        )

    def apply_action(
        self,
        user_id: UUID,
        memory_id: UUID,
        action: MemoryUserControlAction,
        reason: str | None,
    ) -> MemoryControlMutationResponse:
        row = self.repository.get_by_id(memory_id)
        if row is None or row.user_id != user_id:
            raise MemoryUserControlServiceError(404, "Memory item was not found.")

        target_status = _ACTION_TARGET_STATUS[action]
        if row.status == target_status:
            return MemoryControlMutationResponse(
                operation=action,
                applied=False,
                item=self._serialize_item(row),
            )

        metadata_json = self._rebuild_metadata(row.metadata_json)
        governance = metadata_json.setdefault("governance", {})
        control_events = governance.setdefault("control_events", [])
        event = MemoryControlEvent(
            action=action,
            from_status=row.status,
            to_status=target_status,
            reason=reason,
            acted_at=datetime.now(UTC),
        )
        control_events.append(event.model_dump(mode="json"))

        updated = self.repository.update_status_and_metadata(
            memory_id,
            status=target_status,
            metadata_json=metadata_json,
        )
        if updated is None:
            raise MemoryUserControlServiceError(409, "Memory item update did not persist.")

        return MemoryControlMutationResponse(
            operation=action,
            applied=True,
            item=self._serialize_item(updated),
        )

    def _serialize_item(self, row) -> MemoryControlItemSummary:
        return MemoryControlItemSummary(
            memory_id=row.memory_id,
            memory_type=row.memory_type,
            key=row.key,
            value_json=row.value_json,
            text=row.text,
            confidence=row.confidence,
            status=row.status,
            lifecycle_state=resolve_memory_lifecycle_state(row.status, row.expires_at),
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            source_run_id=row.source_run_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata_json=row.metadata_json if isinstance(row.metadata_json, dict) else {},
        )

    def _rebuild_metadata(self, metadata_json: Any) -> dict[str, Any]:
        if not isinstance(metadata_json, dict):
            return {"governance": {"control_events": []}}

        rebuilt = dict(metadata_json)
        governance = rebuilt.get("governance")
        if not isinstance(governance, dict):
            rebuilt["governance"] = {"control_events": []}
            return rebuilt

        control_events = governance.get("control_events")
        if not isinstance(control_events, list):
            governance = dict(governance)
            governance["control_events"] = []
            rebuilt["governance"] = governance
        return rebuilt
