from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.runtime import AgentRun


class AgentRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        user_id: UUID | None,
        case_id: str | None,
        agent_version: str,
        prompt_version: str,
        tool_profile: str,
        world_profile: str,
        failure_profile: str | None,
        status: str,
        metadata_json: dict[str, Any],
        session_id: UUID | None = None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            session_id=session_id,
            case_id=case_id,
            agent_version=agent_version,
            prompt_version=prompt_version,
            tool_profile=tool_profile,
            world_profile=world_profile,
            failure_profile=failure_profile,
            status=status,
            metadata_json=metadata_json,
        )
        self.session.add(run)
        self.session.flush()
        self.session.refresh(run)
        return run

    def update_session_id(self, run_id: UUID, session_id: UUID | None) -> AgentRun | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None

        run.session_id = session_id
        self.session.flush()
        self.session.refresh(run)
        return run

    def get_by_id(self, run_id: UUID) -> AgentRun | None:
        return self.session.get(AgentRun, run_id)

    def update_status(self, run_id: UUID, status: str) -> AgentRun | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None

        run.status = status
        self.session.flush()
        self.session.refresh(run)
        return run

    def update_metadata_json(self, run_id: UUID, metadata_json: dict[str, Any]) -> AgentRun | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None

        run.metadata_json = metadata_json
        self.session.flush()
        self.session.refresh(run)
        return run
