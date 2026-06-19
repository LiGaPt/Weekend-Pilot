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
    MemoryCreateRequest,
    MemoryDetailResponse,
    MemoryUpdateRequest,
    MemoryUserControlAction,
)
from backend.app.memory_governance_audit import (
    classify_memory_governance_audit,
    normalize_supported_preference_value,
)
from backend.app.memory_lifecycle import normalize_memory_status, resolve_memory_lifecycle_state
from backend.app.repositories import MemoryItemRepository


_ACTION_TARGET_STATUS: dict[MemoryUserControlAction, str] = {
    "activate": "active",
    "disable": "disabled",
    "suppress": "ignored",
    "expire": "expired",
    "mark_candidate": "candidate",
}
_SUPPORTED_MEMORY_TYPE = "preference"
_SUPPORTED_MEMORY_KEYS = {"activity_style", "spouse_lighter_meals"}
_CREATE_CHANGED_FIELDS = [
    "memory_type",
    "key",
    "value_json",
    "text",
    "confidence",
    "status",
    "expires_at",
    "source_run_id",
    "source_langsmith_trace_id",
]
_CANONICAL_VALUE_JSON_KEYS = {"preference"}


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

    def get_item(self, user_id: UUID, memory_id: UUID) -> MemoryDetailResponse:
        row = self.repository.get_for_user(user_id, memory_id)
        if row is None:
            raise MemoryUserControlServiceError(404, "Memory item was not found.")
        return MemoryDetailResponse(**self._serialize_item(row).model_dump())

    def create_item(
        self,
        user_id: UUID,
        request: MemoryCreateRequest,
    ) -> MemoryControlMutationResponse:
        normalized_value = self._validate_memory_payload(
            memory_type=request.memory_type,
            key=request.key,
            value_json=request.value_json,
            text=request.text,
        )
        existing = self.repository.get_by_user_memory_key(user_id, request.memory_type, request.key)
        if existing is not None:
            raise MemoryUserControlServiceError(409, "Memory item already exists for this user and key.")

        normalized_status = normalize_memory_status(request.status)
        metadata_json = self._rebuild_metadata({})
        self._append_governance_event(
            metadata_json=metadata_json,
            action="create",
            from_status=None,
            to_status=normalized_status,
            reason=request.reason,
            changed_fields=_CREATE_CHANGED_FIELDS,
        )
        self._append_minimization_event(
            metadata_json=metadata_json,
            action="create",
            reason=request.reason,
            normalized_value=normalized_value,
            dropped_text=bool(request.text),
            dropped_value_keys=self._dropped_value_keys(request.value_json),
        )
        created = self.repository.create(
            user_id=user_id,
            memory_type=request.memory_type,
            key=request.key,
            value_json=self._canonical_value_json(normalized_value),
            text=None,
            confidence=request.confidence,
            source_run_id=request.source_run_id,
            source_langsmith_trace_id=request.source_langsmith_trace_id,
            expires_at=request.expires_at,
            status=normalized_status,
            metadata_json=metadata_json,
        )
        return MemoryControlMutationResponse(
            operation="create",
            applied=True,
            item=self._serialize_item(created),
        )

    def update_item(
        self,
        user_id: UUID,
        memory_id: UUID,
        request: MemoryUpdateRequest,
    ) -> MemoryControlMutationResponse:
        row = self.repository.get_for_user(user_id, memory_id)
        if row is None:
            raise MemoryUserControlServiceError(404, "Memory item was not found.")

        normalized_value = self._validate_memory_payload(
            memory_type=row.memory_type,
            key=row.key,
            value_json=request.value_json,
            text=request.text,
        )
        canonical_value_json = self._canonical_value_json(normalized_value)
        changed_fields: list[str] = []
        if row.value_json != canonical_value_json:
            changed_fields.append("value_json")
        if row.text is not None:
            changed_fields.append("text")
        if row.confidence != request.confidence:
            changed_fields.append("confidence")
        if row.expires_at != request.expires_at:
            changed_fields.append("expires_at")

        if not changed_fields:
            return MemoryControlMutationResponse(
                operation="update",
                applied=False,
                item=self._serialize_item(row),
            )

        metadata_json = self._rebuild_metadata(row.metadata_json)
        self._append_governance_event(
            metadata_json=metadata_json,
            action="update",
            from_status=row.status,
            to_status=row.status,
            reason=request.reason,
            changed_fields=changed_fields,
        )
        self._append_minimization_event(
            metadata_json=metadata_json,
            action="update",
            reason=request.reason,
            normalized_value=normalized_value,
            dropped_text=bool(request.text),
            dropped_value_keys=self._dropped_value_keys(request.value_json),
        )
        updated = self.repository.update(
            memory_id,
            value_json=canonical_value_json,
            text=None,
            confidence=request.confidence,
            source_run_id=row.source_run_id,
            source_langsmith_trace_id=row.source_langsmith_trace_id,
            expires_at=request.expires_at,
            status=row.status,
            metadata_json=metadata_json,
        )
        if updated is None:
            raise MemoryUserControlServiceError(409, "Memory item update did not persist.")
        return MemoryControlMutationResponse(
            operation="update",
            applied=True,
            item=self._serialize_item(updated),
        )

    def apply_action(
        self,
        user_id: UUID,
        memory_id: UUID,
        action: MemoryUserControlAction,
        reason: str | None,
    ) -> MemoryControlMutationResponse:
        row = self.repository.get_for_user(user_id, memory_id)
        if row is None:
            raise MemoryUserControlServiceError(404, "Memory item was not found.")

        target_status = _ACTION_TARGET_STATUS[action]
        if row.status == target_status:
            return MemoryControlMutationResponse(
                operation=action,
                applied=False,
                item=self._serialize_item(row),
            )

        metadata_json = self._rebuild_metadata(row.metadata_json)
        self._append_governance_event(
            metadata_json=metadata_json,
            action=action,
            from_status=row.status,
            to_status=target_status,
            reason=reason,
            changed_fields=["status"],
        )

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

    def delete_item(
        self,
        user_id: UUID,
        memory_id: UUID,
        reason: str | None,
    ) -> MemoryControlMutationResponse:
        return self.apply_action(user_id, memory_id, "suppress", reason)

    def _serialize_item(self, row) -> MemoryControlItemSummary:
        lifecycle_state = resolve_memory_lifecycle_state(row.status, row.expires_at)
        return MemoryControlItemSummary(
            memory_id=row.memory_id,
            memory_type=row.memory_type,
            key=row.key,
            value_json=row.value_json,
            text=row.text,
            confidence=row.confidence,
            status=row.status,
            lifecycle_state=lifecycle_state,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            source_run_id=row.source_run_id,
            source_langsmith_trace_id=row.source_langsmith_trace_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata_json=row.metadata_json if isinstance(row.metadata_json, dict) else {},
            governance_audit=classify_memory_governance_audit(
                memory_type=row.memory_type,
                key=row.key,
                value_json=row.value_json,
                text=row.text,
                confidence=row.confidence,
                status=row.status,
                expires_at=row.expires_at,
                lifecycle_state=lifecycle_state,
            ),
        )

    def _rebuild_metadata(self, metadata_json: Any) -> dict[str, Any]:
        if not isinstance(metadata_json, dict):
            return {"governance": {"control_events": [], "minimization_events": []}}

        rebuilt = dict(metadata_json)
        governance = rebuilt.get("governance")
        if not isinstance(governance, dict):
            rebuilt["governance"] = {"control_events": [], "minimization_events": []}
            return rebuilt

        if not isinstance(governance.get("control_events"), list):
            governance = dict(governance)
            governance["control_events"] = []
        if not isinstance(governance.get("minimization_events"), list):
            governance = dict(governance)
            governance["minimization_events"] = []
        rebuilt["governance"] = governance
        return rebuilt

    def _append_governance_event(
        self,
        *,
        metadata_json: dict[str, Any],
        action: str,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        changed_fields: list[str],
    ) -> None:
        governance = metadata_json.setdefault("governance", {})
        control_events = governance.setdefault("control_events", [])
        event = MemoryControlEvent(
            action=action,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            acted_at=datetime.now(UTC),
            changed_fields=changed_fields,
        )
        control_events.append(event.model_dump(mode="json"))

    def _append_minimization_event(
        self,
        *,
        metadata_json: dict[str, Any],
        action: str,
        reason: str | None,
        normalized_value: str,
        dropped_text: bool,
        dropped_value_keys: list[str],
    ) -> None:
        governance = metadata_json.setdefault("governance", {})
        minimization_events = governance.setdefault("minimization_events", [])
        minimization_events.append(
            {
                "schema_version": "memory_audit_minimization_v0",
                "action": action,
                "actor": "user",
                "source": "internal_memory_api_v1",
                "reason": reason,
                "normalized_value": normalized_value,
                "dropped_text": dropped_text,
                "dropped_value_keys": dropped_value_keys,
                "acted_at": datetime.now(UTC).isoformat(),
            }
        )

    def _validate_memory_payload(
        self,
        *,
        memory_type: str,
        key: str,
        value_json: dict[str, Any],
        text: str | None,
    ) -> str:
        if memory_type != _SUPPORTED_MEMORY_TYPE:
            raise MemoryUserControlServiceError(400, f"Unsupported memory type: {memory_type!r}")
        if key not in _SUPPORTED_MEMORY_KEYS:
            raise MemoryUserControlServiceError(400, f"Unsupported memory key: {key!r}")

        try:
            normalized = normalize_supported_preference_value(key=key, value_json=value_json, text=text)
        except ValueError as exc:
            raise MemoryUserControlServiceError(400, str(exc)) from exc
        if normalized is None:
            raise MemoryUserControlServiceError(400, "Unsupported memory value for this key.")
        return normalized

    def _canonical_value_json(self, normalized_value: str) -> dict[str, str]:
        return {"preference": normalized_value}

    def _dropped_value_keys(self, value_json: dict[str, Any]) -> list[str]:
        if not isinstance(value_json, dict):
            return []
        return sorted(key for key in value_json if key not in _CANONICAL_VALUE_JSON_KEYS)
