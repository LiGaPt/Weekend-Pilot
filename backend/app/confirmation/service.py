from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.confirmation.errors import PlanConfirmationError
from backend.app.confirmation.schemas import ConfirmationResult, ConfirmedActionSpec
from backend.app.models.runtime import Plan
from backend.app.repositories import PlanRepository


class HumanConfirmationService:
    service_version = "human_confirmation_v1"
    _EXECUTION_FIELD_KEYS = {"idempotency_key", "confirmation_id", "action_id"}
    _WRITE_ACTION_TYPES = {
        "join_queue",
        "reserve_restaurant",
        "book_ticket",
        "order_addon",
        "send_message",
    }

    def __init__(self, plans: PlanRepository) -> None:
        self.plans = plans

    def confirm_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
        confirmed_by: str,
        source: str = "unknown",
        confirmed_at: datetime | None = None,
    ) -> ConfirmationResult:
        plan = self._load_plan_for_confirmation(run_id, plan_id)
        if plan.status == "confirmed":
            return self._result_from_plan(plan)
        if plan.status == "declined":
            raise PlanConfirmationError("Declined plans cannot be confirmed.")
        if plan.status != "selected":
            raise PlanConfirmationError("Only selected plans can be confirmed.")

        plan_json = self._reviewed_plan_json(plan)
        actions = self._confirmed_actions(plan, plan_json)
        timestamp = confirmed_at or datetime.now(UTC)
        confirmation_id = self._confirmation_id(run_id, plan_id)
        updated_json = deepcopy(plan_json)
        updated_json["confirmation"] = {
            "schema_version": self.service_version,
            "confirmation_id": confirmation_id,
            "status": "confirmed",
            "confirmed_by": confirmed_by,
            "source": source,
            "confirmed_at": timestamp.isoformat(),
            "action_count": len(actions),
            "service_version": self.service_version,
        }
        updated_json["confirmed_actions"] = [
            action.model_dump(mode="json")
            for action in actions
        ]

        plan.status = "confirmed"
        updated = self.plans.update_plan_json(plan.plan_id, updated_json)
        if updated is None:
            raise PlanConfirmationError("Plan disappeared during confirmation.")
        updated.status = "confirmed"
        self.plans.session.flush()
        self.plans.session.refresh(updated)
        return self._result_from_plan(updated)

    def decline_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
        declined_by: str,
        source: str = "unknown",
        declined_at: datetime | None = None,
        reason: str | None = None,
    ) -> ConfirmationResult:
        plan = self._load_plan_for_confirmation(run_id, plan_id)
        if plan.status == "declined":
            return self._result_from_plan(plan)
        if plan.status == "confirmed":
            raise PlanConfirmationError("Confirmed plans cannot be declined.")
        if plan.status != "selected":
            raise PlanConfirmationError("Only selected plans can be declined.")

        plan_json = self._reviewed_plan_json(plan)
        timestamp = declined_at or datetime.now(UTC)
        confirmation_id = self._confirmation_id(run_id, plan_id)
        updated_json = deepcopy(plan_json)
        updated_json["confirmation"] = {
            "schema_version": self.service_version,
            "confirmation_id": confirmation_id,
            "status": "declined",
            "declined_by": declined_by,
            "source": source,
            "declined_at": timestamp.isoformat(),
            "reason": reason,
            "action_count": 0,
            "service_version": self.service_version,
        }
        updated_json["confirmed_actions"] = []

        plan.status = "declined"
        updated = self.plans.update_plan_json(plan.plan_id, updated_json)
        if updated is None:
            raise PlanConfirmationError("Plan disappeared during decline.")
        updated.status = "declined"
        self.plans.session.flush()
        self.plans.session.refresh(updated)
        return self._result_from_plan(updated)

    def _load_plan_for_confirmation(self, run_id: UUID, plan_id: UUID) -> Plan:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise PlanConfirmationError("Plan does not exist.")
        if plan.run_id != run_id:
            raise PlanConfirmationError("Plan does not belong to the requested run.")
        if not plan.selected:
            raise PlanConfirmationError("Plan must be selected before confirmation.")
        return plan

    def _reviewed_plan_json(self, plan: Plan) -> dict[str, Any]:
        plan_json = plan.plan_json
        if not isinstance(plan_json, dict):
            raise PlanConfirmationError("Plan JSON is malformed.")
        if plan_json.get("schema_version") != "reviewed_plan_v1":
            raise PlanConfirmationError("Plan JSON is not a reviewed plan.")
        if plan_json.get("safe_to_present") is not True:
            raise PlanConfirmationError("Plan is not safe to present.")
        draft = plan_json.get("draft")
        if not isinstance(draft, dict):
            raise PlanConfirmationError("Plan JSON is missing draft payload.")
        actions = draft.get("proposed_actions")
        if actions is not None and not isinstance(actions, list):
            raise PlanConfirmationError("Draft proposed actions must be a list.")
        return plan_json

    def _confirmed_actions(
        self,
        plan: Plan,
        plan_json: dict[str, Any],
    ) -> list[ConfirmedActionSpec]:
        draft = plan_json["draft"]
        proposed_actions = draft.get("proposed_actions") or []
        confirmed_actions = []
        seen_keys = set()

        for index, action in enumerate(proposed_actions, start=1):
            if not isinstance(action, dict):
                raise PlanConfirmationError("Proposed action must be an object.")
            self._validate_proposed_action(action)
            action_ref = action["action_ref"]
            idempotency_key = self._idempotency_key(plan.run_id, plan.plan_id, action_ref)
            if idempotency_key in seen_keys:
                raise PlanConfirmationError("Duplicate confirmed action idempotency key.")
            seen_keys.add(idempotency_key)
            confirmed_actions.append(
                ConfirmedActionSpec(
                    action_ref=action_ref,
                    execution_order=index,
                    tool_name=action["action_type"],
                    target_id=action["target_id"],
                    payload=deepcopy(action.get("payload") or {}),
                    idempotency_key=idempotency_key,
                    user_confirmed=True,
                    reason=action["reason"],
                )
            )
        return confirmed_actions

    def _validate_proposed_action(self, action: dict[str, Any]) -> None:
        for key in ("action_ref", "action_type", "target_id", "reason"):
            if not isinstance(action.get(key), str) or not action[key]:
                raise PlanConfirmationError(f"Proposed action is missing {key}.")
        if action["action_type"] not in self._WRITE_ACTION_TYPES:
            raise PlanConfirmationError("Proposed action type is not a registered write action.")
        if action.get("requires_confirmation") is not True:
            raise PlanConfirmationError("Proposed action must require confirmation.")
        payload = action.get("payload")
        if payload is not None and not isinstance(payload, dict):
            raise PlanConfirmationError("Proposed action payload must be an object.")
        forbidden_keys = self._find_forbidden_keys(action)
        if forbidden_keys:
            raise PlanConfirmationError(
                f"Proposed action contains pre-confirmation execution fields: {forbidden_keys}"
            )

    def _find_forbidden_keys(self, value: Any) -> list[str]:
        matches = []
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(key, str) and key.casefold() in self._EXECUTION_FIELD_KEYS:
                    matches.append(key)
                matches.extend(self._find_forbidden_keys(child))
        elif isinstance(value, list):
            for item in value:
                matches.extend(self._find_forbidden_keys(item))
        return sorted(set(matches))

    def _confirmation_id(self, run_id: UUID, plan_id: UUID) -> str:
        return f"confirmation:{run_id}:{plan_id}"

    def _idempotency_key(self, run_id: UUID, plan_id: UUID, action_ref: str) -> str:
        key = f"confirm:{run_id}:{plan_id}:{action_ref}"
        if not key:
            raise PlanConfirmationError("Generated idempotency key is empty.")
        if len(key) > 255:
            raise PlanConfirmationError("Generated idempotency key exceeds 255 characters.")
        return key

    def _result_from_plan(self, plan: Plan) -> ConfirmationResult:
        plan_json = self._reviewed_plan_json(plan)
        confirmation = plan_json.get("confirmation")
        if not isinstance(confirmation, dict):
            raise PlanConfirmationError("Plan is missing confirmation metadata.")
        status = confirmation.get("status")
        if status not in {"confirmed", "declined"}:
            raise PlanConfirmationError("Plan confirmation status is invalid.")

        raw_actions = plan_json.get("confirmed_actions") or []
        if not isinstance(raw_actions, list):
            raise PlanConfirmationError("Confirmed actions must be a list.")

        return ConfirmationResult(
            run_id=plan.run_id,
            plan_id=plan.plan_id,
            status=status,
            confirmation_id=str(confirmation.get("confirmation_id")),
            selected=plan.selected,
            confirmed_actions=[
                ConfirmedActionSpec.model_validate(action)
                for action in raw_actions
            ],
            service_version=self.service_version,
        )
