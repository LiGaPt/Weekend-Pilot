from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.app.models.runtime import Plan
from backend.app.planning.itinerary_drafts import ItineraryDraft, ItineraryDraftResult
from backend.app.plans.errors import PlanPersistenceError, PlanSelectionError
from backend.app.plans.schemas import (
    PersistedPlan,
    PersistedPlanResult,
    PlanPersistenceStatus,
    SkippedDraft,
    SkippedPlanReason,
)
from backend.app.repositories import PlanRepository
from backend.app.review.schemas import FinalReviewResult, ReviewedDraft


class ReviewedPlanPersistenceService:
    service_version = "reviewed_plan_persistence_v1"

    def __init__(self, plans: PlanRepository) -> None:
        self.plans = plans

    def persist_reviewed_drafts(
        self,
        review: FinalReviewResult,
        drafts: ItineraryDraftResult,
    ) -> PersistedPlanResult:
        if review.run_id != drafts.run_id:
            raise PlanPersistenceError("Review and draft run IDs do not match.")
        if review.provider_profile != drafts.provider_profile:
            raise PlanPersistenceError("Review and draft provider profiles do not match.")

        result = PersistedPlanResult(
            run_id=review.run_id,
            service_version=self.service_version,
        )

        if review.safe_to_present is False:
            result.skipped_drafts.extend(
                self._skipped(
                    reviewed_draft,
                    "review_blocked",
                    "Top-level final review blocked presentation for this run.",
                )
                for reviewed_draft in review.reviewed_drafts
            )
            return result

        draft_by_id = {draft.draft_id: draft for draft in drafts.drafts}
        for reviewed_draft in review.reviewed_drafts:
            if reviewed_draft.safe_to_present is False:
                result.skipped_drafts.append(
                    self._skipped(
                        reviewed_draft,
                        "not_safe_to_present",
                        "Reviewed draft is not safe to present.",
                    )
                )
                continue

            draft = draft_by_id.get(reviewed_draft.draft_id)
            if draft is None:
                result.skipped_drafts.append(
                    self._skipped(
                        reviewed_draft,
                        "draft_not_found",
                        "Reviewed draft does not match an itinerary draft.",
                    )
                )
                continue

            existing = self.plans.find_by_run_and_draft_id(review.run_id, draft.draft_id)
            if existing is not None:
                result.persisted_plans.append(
                    self._to_persisted_plan(existing, persistence_status="already_exists")
                )
                continue

            plan = self.plans.create(
                run_id=review.run_id,
                status="reviewed",
                selected=False,
                plan_json=self._build_plan_json(review, reviewed_draft, draft, drafts),
            )
            result.persisted_plans.append(
                self._to_persisted_plan(plan, persistence_status="created")
            )

        return result

    def select_plan(self, run_id: UUID, plan_id: UUID) -> PersistedPlan:
        selected = self.plans.select_for_run(run_id, plan_id)
        if selected is None:
            raise PlanSelectionError("Plan does not exist for the requested run.")
        return self._to_persisted_plan(selected)

    def _build_plan_json(
        self,
        review: FinalReviewResult,
        reviewed_draft: ReviewedDraft,
        draft: ItineraryDraft,
        drafts: ItineraryDraftResult,
    ) -> dict[str, Any]:
        return {
            "schema_version": "reviewed_plan_v1",
            "persistence_version": self.service_version,
            "run_id": str(review.run_id),
            "provider_profile": review.provider_profile,
            "draft_id": draft.draft_id,
            "status": "reviewed",
            "safe_to_present": reviewed_draft.safe_to_present,
            "review_decision": reviewed_draft.decision,
            "draft": draft.model_dump(mode="json"),
            "reviewed_draft": reviewed_draft.model_dump(mode="json"),
            "final_review": {
                "decision": review.decision,
                "safe_to_present": review.safe_to_present,
                "gate_version": review.gate_version,
            },
            "source_versions": {
                "generator_version": drafts.generator_version,
                "gate_version": review.gate_version,
                "persistence_version": self.service_version,
            },
        }

    def _to_persisted_plan(
        self,
        plan: Plan,
        persistence_status: PlanPersistenceStatus | None = None,
    ) -> PersistedPlan:
        plan_json = plan.plan_json if isinstance(plan.plan_json, dict) else {}
        return PersistedPlan(
            plan_id=plan.plan_id,
            run_id=plan.run_id,
            draft_id=str(plan_json.get("draft_id", "")),
            status=plan.status,
            selected=plan.selected,
            safe_to_present=bool(plan_json.get("safe_to_present", False)),
            review_decision=str(plan_json.get("review_decision", "")),
            persistence_status=persistence_status,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    def _skipped(
        self,
        reviewed_draft: ReviewedDraft,
        reason: SkippedPlanReason,
        message: str,
    ) -> SkippedDraft:
        return SkippedDraft(
            draft_id=reviewed_draft.draft_id,
            reason=reason,
            review_decision=reviewed_draft.decision,
            message=message,
        )
