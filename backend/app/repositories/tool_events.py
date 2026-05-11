from typing import Any
from uuid import UUID

from sqlalchemy import select
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
        event = ToolEvent(
            run_id=run_id,
            tool_name=tool_name,
            tool_type=tool_type,
            provider=provider,
            request_json=request_json,
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
        statement = (
            select(ToolEvent)
            .where(ToolEvent.run_id == run_id)
            .order_by(ToolEvent.created_at, ToolEvent.event_id)
        )
        return list(self.session.scalars(statement).all())
