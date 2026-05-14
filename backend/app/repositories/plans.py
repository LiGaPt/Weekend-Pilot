from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.runtime import Plan


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        run_id: UUID,
        status: str,
        plan_json: dict[str, Any],
        selected: bool = False,
    ) -> Plan:
        plan = Plan(
            run_id=run_id,
            status=status,
            plan_json=plan_json,
            selected=selected,
        )
        self.session.add(plan)
        self.session.flush()
        self.session.refresh(plan)
        return plan

    def get_by_id(self, plan_id: UUID) -> Plan | None:
        return self.session.get(Plan, plan_id)

    def list_for_run(self, run_id: UUID) -> list[Plan]:
        statement = (
            select(Plan)
            .where(Plan.run_id == run_id)
            .order_by(Plan.created_at, Plan.plan_id)
        )
        return list(self.session.scalars(statement).all())

    def find_by_run_and_draft_id(self, run_id: UUID, draft_id: str) -> Plan | None:
        for plan in self.list_for_run(run_id):
            if isinstance(plan.plan_json, dict) and plan.plan_json.get("draft_id") == draft_id:
                return plan
        return None

    def update_status(self, plan_id: UUID, status: str) -> Plan | None:
        plan = self.get_by_id(plan_id)
        if plan is None:
            return None

        plan.status = status
        self.session.flush()
        self.session.refresh(plan)
        return plan

    def update_plan_json(
        self,
        plan_id: UUID,
        plan_json: dict[str, Any],
    ) -> Plan | None:
        plan = self.get_by_id(plan_id)
        if plan is None:
            return None

        plan.plan_json = plan_json
        self.session.flush()
        self.session.refresh(plan)
        return plan

    def get_selected_for_run(self, run_id: UUID) -> Plan | None:
        statement = select(Plan).where(
            Plan.run_id == run_id,
            Plan.selected.is_(True),
        )
        return self.session.scalar(statement)

    def select_for_run(self, run_id: UUID, plan_id: UUID) -> Plan | None:
        target = self.get_by_id(plan_id)
        if target is None or target.run_id != run_id:
            return None

        for plan in self.list_for_run(run_id):
            if plan.plan_id == plan_id:
                plan.selected = True
                plan.status = "selected"
            else:
                plan.selected = False
                if plan.status == "selected":
                    plan.status = "reviewed"

        self.session.flush()
        self.session.refresh(target)
        return target
