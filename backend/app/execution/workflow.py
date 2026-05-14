from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.execution.errors import ExecutionWorkflowError
from backend.app.execution.schemas import ExecutionActionResult, ExecutionWorkflowResult
from backend.app.models.runtime import Plan
from backend.app.repositories import PlanRepository
from backend.app.tool_gateway import ToolGateway, ToolGatewayRequest
from backend.app.tool_gateway.registry import WRITE_TOOLS


class DeterministicExecutionWorkflow:
    workflow_version = "deterministic_execution_workflow_v1"
    _SUCCESS_STATUSES = {"succeeded", "idempotent_replay"}
    _FAILURE_STATUSES = {"failed", "blocked", "rate_limited"}
    _ALLOWED_GATEWAY_STATUSES = _SUCCESS_STATUSES | _FAILURE_STATUSES
    _ALLOWED_PLAN_STATUSES = {
        "confirmed",
        "executed",
        "partially_executed",
        "execution_failed",
        "execution_skipped",
    }

    def __init__(
        self,
        plans: PlanRepository,
        gateway: ToolGateway,
    ) -> None:
        self.plans = plans
        self.gateway = gateway

    def execute_confirmed_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
    ) -> ExecutionWorkflowResult:
        started_at = datetime.now(UTC)
        plan = self._load_executable_plan(run_id, plan_id)
        plan_json = self._plan_json(plan)
        actions = self._confirmed_actions(plan_json)

        if not actions:
            result = ExecutionWorkflowResult(
                run_id=run_id,
                plan_id=plan_id,
                status="skipped",
                plan_status="execution_skipped",
                action_results=[],
                succeeded_count=0,
                failed_count=0,
                workflow_version=self.workflow_version,
            )
            self._persist_execution(plan, plan_json, result, started_at, datetime.now(UTC))
            return result

        action_results = []
        for action in actions:
            gateway_result = self.gateway.invoke(
                ToolGatewayRequest(
                    run_id=run_id,
                    tool_name=action["tool_name"],
                    payload=deepcopy(action.get("payload") or {}),
                    provider=plan_json.get("provider_profile"),
                    user_confirmed=True,
                    target_id=action["target_id"],
                    idempotency_key=action["idempotency_key"],
                )
            )
            if gateway_result.status not in self._ALLOWED_GATEWAY_STATUSES:
                raise ExecutionWorkflowError("Tool Gateway returned an unsupported execution status.")
            action_results.append(
                ExecutionActionResult(
                    action_ref=action["action_ref"],
                    execution_order=action["execution_order"],
                    tool_name=action["tool_name"],
                    target_id=action["target_id"],
                    idempotency_key=action["idempotency_key"],
                    status=gateway_result.status,
                    action_id=gateway_result.action_id,
                    tool_event_id=gateway_result.tool_event_id,
                    response_json=gateway_result.response_json,
                    error_json=gateway_result.error_json,
                )
            )

        succeeded_count = sum(1 for item in action_results if item.status in self._SUCCESS_STATUSES)
        failed_count = sum(1 for item in action_results if item.status in self._FAILURE_STATUSES)
        workflow_status, plan_status = self._status_pair(succeeded_count, failed_count)

        result = ExecutionWorkflowResult(
            run_id=run_id,
            plan_id=plan_id,
            status=workflow_status,
            plan_status=plan_status,
            action_results=action_results,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            workflow_version=self.workflow_version,
        )
        self._persist_execution(plan, plan_json, result, started_at, datetime.now(UTC))
        return result

    def _load_executable_plan(self, run_id: UUID, plan_id: UUID) -> Plan:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise ExecutionWorkflowError("Plan does not exist.")
        if plan.run_id != run_id:
            raise ExecutionWorkflowError("Plan does not belong to the requested run.")
        if not plan.selected:
            raise ExecutionWorkflowError("Plan must be selected before execution.")
        if plan.status == "declined":
            raise ExecutionWorkflowError("Declined plans cannot be executed.")
        if plan.status not in self._ALLOWED_PLAN_STATUSES:
            raise ExecutionWorkflowError("Plan must be confirmed before execution.")
        return plan

    def _plan_json(self, plan: Plan) -> dict[str, Any]:
        plan_json = plan.plan_json
        if not isinstance(plan_json, dict):
            raise ExecutionWorkflowError("Plan JSON is malformed.")
        if plan_json.get("schema_version") != "reviewed_plan_v1":
            raise ExecutionWorkflowError("Plan JSON is not a reviewed plan.")
        confirmation = plan_json.get("confirmation")
        if not isinstance(confirmation, dict):
            raise ExecutionWorkflowError("Plan is missing confirmation metadata.")
        if confirmation.get("status") != "confirmed":
            raise ExecutionWorkflowError("Plan must be confirmed before execution.")
        provider_profile = plan_json.get("provider_profile")
        if not isinstance(provider_profile, str) or not provider_profile:
            raise ExecutionWorkflowError("Plan provider profile is missing.")
        return plan_json

    def _confirmed_actions(self, plan_json: dict[str, Any]) -> list[dict[str, Any]]:
        actions = plan_json.get("confirmed_actions")
        if actions is None:
            raise ExecutionWorkflowError("Plan is missing confirmed actions.")
        if not isinstance(actions, list):
            raise ExecutionWorkflowError("Confirmed actions must be a list.")

        validated = []
        seen_refs = set()
        seen_orders = set()
        for action in actions:
            if not isinstance(action, dict):
                raise ExecutionWorkflowError("Confirmed action must be an object.")
            self._validate_action(action)
            if action["action_ref"] in seen_refs:
                raise ExecutionWorkflowError("Duplicate confirmed action ref.")
            if action["execution_order"] in seen_orders:
                raise ExecutionWorkflowError("Duplicate execution order.")
            seen_refs.add(action["action_ref"])
            seen_orders.add(action["execution_order"])
            validated.append(action)

        return sorted(validated, key=lambda item: item["execution_order"])

    def _validate_action(self, action: dict[str, Any]) -> None:
        if not isinstance(action.get("action_ref"), str) or not action["action_ref"]:
            raise ExecutionWorkflowError("Confirmed action is missing action_ref.")
        if not isinstance(action.get("execution_order"), int) or action["execution_order"] <= 0:
            raise ExecutionWorkflowError("Confirmed action has invalid execution_order.")
        if action.get("tool_name") not in WRITE_TOOLS:
            raise ExecutionWorkflowError("Confirmed action tool must be a write tool.")
        if not isinstance(action.get("target_id"), str) or not action["target_id"]:
            raise ExecutionWorkflowError("Confirmed action is missing target_id.")
        if not isinstance(action.get("idempotency_key"), str) or not action["idempotency_key"]:
            raise ExecutionWorkflowError("Confirmed action is missing idempotency_key.")
        if len(action["idempotency_key"]) > 255:
            raise ExecutionWorkflowError("Confirmed action idempotency_key exceeds 255 characters.")
        if action.get("user_confirmed") is not True:
            raise ExecutionWorkflowError("Confirmed action must set user_confirmed=True.")
        payload = action.get("payload")
        if payload is not None and not isinstance(payload, dict):
            raise ExecutionWorkflowError("Confirmed action payload must be an object.")

    def _status_pair(self, succeeded_count: int, failed_count: int) -> tuple[str, str]:
        if succeeded_count > 0 and failed_count == 0:
            return "succeeded", "executed"
        if succeeded_count > 0 and failed_count > 0:
            return "partially_succeeded", "partially_executed"
        return "failed", "execution_failed"

    def _persist_execution(
        self,
        plan: Plan,
        plan_json: dict[str, Any],
        result: ExecutionWorkflowResult,
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        updated_json = deepcopy(plan_json)
        updated_json["execution"] = {
            "schema_version": "execution_workflow_v1",
            "workflow_version": self.workflow_version,
            "status": result.status,
            "plan_status": result.plan_status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "succeeded_count": result.succeeded_count,
            "failed_count": result.failed_count,
            "action_results": [
                action.model_dump(mode="json")
                for action in result.action_results
            ],
        }
        updated = self.plans.update_status_and_plan_json(
            plan.plan_id,
            result.plan_status,
            updated_json,
        )
        if updated is None:
            raise ExecutionWorkflowError("Plan disappeared during execution persistence.")
