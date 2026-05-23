from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.runtime import ToolEvent


class ToolEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        run_id: UUID,
        tool_name: str,
        tool_type: str,
        provider: str,
        request_json: dict[str, Any],
        response_json: dict[str, Any] | None,
        error_json: dict[str, Any] | None,
        status: str,
        cache_hit: bool,
        latency_ms: int | None,
        langsmith_trace_id: str | None,
    ) -> ToolEvent:
        request_json_with_sequence = dict(request_json)
        if "event_sequence" not in request_json_with_sequence:
            request_json_with_sequence["event_sequence"] = self._next_event_sequence(run_id)
        event = ToolEvent(
            run_id=run_id,
            tool_name=tool_name,
            tool_type=tool_type,
            provider=provider,
            request_json=request_json_with_sequence,
            response_json=response_json,
            error_json=error_json,
            status=status,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            langsmith_trace_id=langsmith_trace_id,
        )
        self.session.add(event)
        self.session.flush()
        self.session.refresh(event)
        return event

    def get_by_id(self, event_id: UUID) -> ToolEvent | None:
        return self.session.get(ToolEvent, event_id)

    def list_for_run(self, run_id: UUID) -> list[ToolEvent]:
        statement = select(ToolEvent).where(ToolEvent.run_id == run_id)
        events = list(self.session.scalars(statement).all())
        return sorted(
            events,
            key=lambda event: (
                self._event_sequence(event),
                str(event.event_id),
            ),
        )

    def _next_event_sequence(self, run_id: UUID) -> int:
        current_count = self.session.scalar(
            select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run_id)
        )
        return int(current_count or 0) + 1

    @staticmethod
    def _event_sequence(event: ToolEvent) -> int:
        request_json = event.request_json if isinstance(event.request_json, dict) else {}
        value = request_json.get("event_sequence")
        try:
            return int(value)
        except (TypeError, ValueError):
            return 1_000_000_000
