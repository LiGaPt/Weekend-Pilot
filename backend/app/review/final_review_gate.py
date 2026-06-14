from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.app.planning.enriched_candidates import CandidateEnrichmentResult, EnrichedCandidate
from backend.app.planning.itinerary_drafts import ItineraryDraft, ItineraryDraftResult
from backend.app.planning.schemas import QueryPlan
from backend.app.review.schemas import FinalReviewResult, ReviewCheck, ReviewDecision, ReviewedDraft


class FinalReviewGate:
    gate_version = "final_review_gate_v1"

    _USABLE_ROUTE_STATUSES = {"succeeded", "cached"}
    _DEFAULT_MIN_DURATION_MINUTES = 240
    _DEFAULT_MAX_DURATION_MINUTES = 360
    _EXECUTION_FIELD_KEYS = {"idempotency_key", "confirmation_id", "action_id"}
    _REQUIRED_TIMELINE_ITEM_TYPES = {"activity", "transfer", "dining"}
    _SENSITIVE_KEY_FRAGMENTS = (
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "prompt",
        "trace",
        "debug",
    )

    def review(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        drafts: ItineraryDraftResult,
        pre_confirmation_action_count: int = 0,
    ) -> FinalReviewResult:
        global_checks = self._global_checks(plan, enrichment, drafts, pre_confirmation_action_count)
        indexes = self._build_enrichment_indexes(enrichment)
        reviewed_drafts = [
            self._review_draft(plan, draft, indexes)
            for draft in drafts.drafts
        ]

        checks = [*global_checks]
        for reviewed_draft in reviewed_drafts:
            checks.extend(reviewed_draft.checks)

        errors = [check for check in checks if check.status == "failed"]
        warnings = [check for check in checks if check.status == "warning"]
        global_errors = [check for check in global_checks if check.status == "failed"]
        safe_drafts = [reviewed for reviewed in reviewed_drafts if reviewed.safe_to_present]

        if global_errors or not safe_drafts:
            decision: ReviewDecision = "blocked"
        elif warnings or any(reviewed.errors for reviewed in reviewed_drafts):
            decision = "approved_with_warnings"
        else:
            decision = "approved"

        return FinalReviewResult(
            run_id=drafts.run_id,
            provider_profile=drafts.provider_profile,
            decision=decision,
            safe_to_present=decision != "blocked",
            reviewed_drafts=reviewed_drafts,
            checks=checks,
            errors=errors,
            warnings=warnings,
            gate_version=self.gate_version,
        )

    def _global_checks(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        drafts: ItineraryDraftResult,
        pre_confirmation_action_count: int,
    ) -> list[ReviewCheck]:
        checks = []
        run_id_matches = enrichment.run_id == drafts.run_id
        provider_matches = (
            plan.provider_profile == enrichment.provider_profile == drafts.provider_profile
        )
        if run_id_matches and provider_matches:
            checks.append(
                self._pass(
                    "run_id_consistency",
                    "Run and provider profile metadata are consistent.",
                    details={
                        "run_id": str(drafts.run_id),
                        "provider_profile": drafts.provider_profile,
                    },
                )
            )
        else:
            checks.append(
                self._fail(
                    "run_id_consistency",
                    "Run or provider profile metadata is inconsistent.",
                    details={
                        "plan_provider_profile": plan.provider_profile,
                        "enrichment_run_id": str(enrichment.run_id),
                        "drafts_run_id": str(drafts.run_id),
                        "enrichment_provider_profile": enrichment.provider_profile,
                        "drafts_provider_profile": drafts.provider_profile,
                    },
                )
            )

        if pre_confirmation_action_count == 0:
            checks.append(
                self._pass(
                    "pre_confirmation_no_actions",
                    "No pre-confirmation write actions were recorded.",
                    details={"pre_confirmation_action_count": pre_confirmation_action_count},
                )
            )
        else:
            checks.append(
                self._fail(
                    "pre_confirmation_no_actions",
                    "Write actions were recorded before user confirmation.",
                    details={"pre_confirmation_action_count": pre_confirmation_action_count},
                )
            )

        if drafts.drafts:
            checks.append(
                self._pass(
                    "draft_exists",
                    "At least one itinerary draft is available for review.",
                    details={"draft_count": len(drafts.drafts)},
                )
            )
        else:
            checks.append(
                self._fail(
                    "draft_exists",
                    "No itinerary drafts are available for review.",
                    details={"draft_count": 0},
                )
            )
        return checks

    def _build_enrichment_indexes(self, enrichment: CandidateEnrichmentResult) -> dict[str, Any]:
        activity_by_id = {
            item.candidate.candidate_id: item
            for item in enrichment.enriched_activity_candidates
        }
        dining_by_id = {
            item.candidate.candidate_id: item
            for item in enrichment.enriched_dining_candidates
        }
        other_by_id = {
            item.candidate.candidate_id: item
            for item in enrichment.enriched_other_candidates
        }
        route_keys = {
            (entry.origin_candidate_id, entry.destination_candidate_id)
            for entry in enrichment.route_matrix
            if entry.status in self._USABLE_ROUTE_STATUSES
        }
        queue_ids_by_dining_id = {}
        for dining in enrichment.enriched_dining_candidates:
            queue = dining.queue
            if isinstance(queue, dict) and isinstance(queue.get("queue_id"), str):
                queue_ids_by_dining_id[dining.candidate.candidate_id] = queue["queue_id"]

        return {
            "activity_by_id": activity_by_id,
            "dining_by_id": dining_by_id,
            "other_by_id": other_by_id,
            "activity_ids": set(activity_by_id),
            "dining_ids": set(dining_by_id),
            "other_ids": set(other_by_id),
            "addon_ids": {
                candidate_id
                for candidate_id, item in other_by_id.items()
                if item.candidate.category == "addon"
            },
            "route_keys": route_keys,
            "queue_ids_by_dining_id": queue_ids_by_dining_id,
        }

    def _review_draft(
        self,
        plan: QueryPlan,
        draft: ItineraryDraft,
        indexes: dict[str, Any],
    ) -> ReviewedDraft:
        draft_id = self._draft_id(draft)
        checks = [
            self._check_activity_present(draft, draft_id),
            self._check_dining_present(draft, draft_id),
            self._check_candidate_ids_verified(draft, draft_id, indexes),
            self._check_dining_availability(draft, draft_id, indexes),
            self._check_route_present(draft, draft_id),
            self._check_route_verified(draft, draft_id, indexes),
            self._check_timeline_duration(plan, draft, draft_id),
            self._check_child_friendly_constraint(plan, draft, draft_id, indexes),
            self._check_dining_preference_constraint(plan, draft, draft_id, indexes),
            self._check_distance_constraint(plan, draft, draft_id),
            self._check_actions_require_confirmation(draft, draft_id),
            self._check_actions_reference_draft_objects(draft, draft_id, indexes),
            self._check_actions_have_no_execution_fields(draft, draft_id),
            self._check_sensitive_payload_scan(draft, draft_id),
        ]
        errors = [check for check in checks if check.status == "failed"]
        warnings = [check for check in checks if check.status == "warning"]

        if errors:
            decision: ReviewDecision = "blocked"
        elif warnings:
            decision = "approved_with_warnings"
        else:
            decision = "approved"

        return ReviewedDraft(
            draft_id=draft_id,
            decision=decision,
            safe_to_present=decision != "blocked",
            checks=checks,
            errors=errors,
            warnings=warnings,
        )

    def _check_activity_present(self, draft: ItineraryDraft, draft_id: str) -> ReviewCheck:
        activity_id = self._activity_id(draft)
        if activity_id:
            return self._pass(
                "activity_present",
                "Draft includes an activity candidate.",
                draft_id=draft_id,
                details={"activity_id": activity_id},
            )
        return self._fail(
            "activity_present",
            "Draft does not include an activity candidate.",
            draft_id=draft_id,
        )

    def _check_dining_present(self, draft: ItineraryDraft, draft_id: str) -> ReviewCheck:
        dining_id = self._dining_id(draft)
        if dining_id:
            return self._pass(
                "dining_present",
                "Draft includes a dining candidate.",
                draft_id=draft_id,
                details={"dining_id": dining_id},
            )
        return self._fail(
            "dining_present",
            "Draft does not include a dining candidate.",
            draft_id=draft_id,
        )

    def _check_candidate_ids_verified(
        self,
        draft: ItineraryDraft,
        draft_id: str,
        indexes: dict[str, Any],
    ) -> ReviewCheck:
        activity_id = self._activity_id(draft)
        dining_id = self._dining_id(draft)
        missing = []
        if not activity_id or activity_id not in indexes["activity_ids"]:
            missing.append({"candidate_role": "activity", "candidate_id": activity_id})
        if not dining_id or dining_id not in indexes["dining_ids"]:
            missing.append({"candidate_role": "dining", "candidate_id": dining_id})
        if missing:
            return self._fail(
                "candidate_ids_verified",
                "Draft candidate IDs are not fully backed by enrichment evidence.",
                draft_id=draft_id,
                details={"missing": missing},
            )
        return self._pass(
            "candidate_ids_verified",
            "Draft candidate IDs are backed by enrichment evidence.",
            draft_id=draft_id,
            details={"activity_id": activity_id, "dining_id": dining_id},
        )

    def _check_dining_availability(
        self,
        draft: ItineraryDraft,
        draft_id: str,
        indexes: dict[str, Any],
    ) -> ReviewCheck:
        dining_id = self._dining_id(draft)
        dining = indexes["dining_by_id"].get(dining_id)
        if dining is None:
            return self._fail(
                "dining_availability",
                "Draft dining candidate availability cannot be verified.",
                draft_id=draft_id,
                details={"dining_id": dining_id, "availability_status": "missing_evidence"},
            )

        table = dining.table_availability if isinstance(dining.table_availability, dict) else {}
        queue = dining.queue if isinstance(dining.queue, dict) else {}
        table_available = table.get("available")
        queue_status = queue.get("status")
        details = {
            "dining_id": dining_id,
            "table_available": table_available,
            "queue_status": queue_status,
        }
        if queue_status == "closed" and table_available is False:
            return self._fail(
                "dining_availability",
                "Draft dining candidate is blocked because both table and queue access are unavailable.",
                draft_id=draft_id,
                details={**details, "availability_status": "table_and_queue_unavailable"},
            )
        if queue_status == "closed":
            return self._fail(
                "dining_availability",
                "Draft dining candidate is blocked because queue access is closed.",
                draft_id=draft_id,
                details={**details, "availability_status": "queue_closed"},
            )
        if table_available is False:
            return self._fail(
                "dining_availability",
                "Draft dining candidate is blocked because table availability is unavailable.",
                draft_id=draft_id,
                details={**details, "availability_status": "table_unavailable"},
            )
        return self._pass(
            "dining_availability",
            "Draft dining candidate has usable table and queue availability evidence.",
            draft_id=draft_id,
            details={**details, "availability_status": "usable"},
        )

    def _check_route_present(self, draft: ItineraryDraft, draft_id: str) -> ReviewCheck:
        route = getattr(draft, "route", None)
        if route is not None:
            return self._pass(
                "route_present",
                "Draft includes a route.",
                draft_id=draft_id,
            )
        return self._fail(
            "route_present",
            "Draft does not include a route.",
            draft_id=draft_id,
        )

    def _check_route_verified(
        self,
        draft: ItineraryDraft,
        draft_id: str,
        indexes: dict[str, Any],
    ) -> ReviewCheck:
        route = getattr(draft, "route", None)
        activity_id = self._activity_id(draft)
        dining_id = self._dining_id(draft)
        if route is None or not activity_id or not dining_id:
            return self._fail(
                "route_verified",
                "Draft route cannot be verified without route, activity, and dining IDs.",
                draft_id=draft_id,
                details={"activity_id": activity_id, "dining_id": dining_id},
            )

        origin_id = getattr(route, "origin_candidate_id", None)
        destination_id = getattr(route, "destination_candidate_id", None)
        route_key = (origin_id, destination_id)
        if origin_id != activity_id or destination_id != dining_id:
            return self._fail(
                "route_verified",
                "Draft route does not connect the selected activity to the selected dining candidate.",
                draft_id=draft_id,
                details={
                    "activity_id": activity_id,
                    "dining_id": dining_id,
                    "route_origin_candidate_id": origin_id,
                    "route_destination_candidate_id": destination_id,
                },
            )

        if route_key not in indexes["route_keys"]:
            return self._fail(
                "route_verified",
                "Draft route is not present in usable enrichment route evidence.",
                draft_id=draft_id,
                details={"route_key": list(route_key)},
            )

        return self._pass(
            "route_verified",
            "Draft route is backed by usable enrichment route evidence.",
            draft_id=draft_id,
            details={"route_key": list(route_key)},
        )

    def _check_timeline_duration(
        self,
        plan: QueryPlan,
        draft: ItineraryDraft,
        draft_id: str,
    ) -> ReviewCheck:
        timeline = getattr(draft, "timeline", None) or []
        if not timeline:
            return self._fail(
                "timeline_duration",
                "Draft timeline is empty.",
                draft_id=draft_id,
            )

        invalid_items = []
        durations = []
        for item in timeline:
            item_type = getattr(item, "item_type", None)
            duration = getattr(item, "duration_minutes", None)
            durations.append(duration)
            if not isinstance(duration, int):
                invalid_items.append({"item_type": item_type, "duration_minutes": duration})
            elif item_type in self._REQUIRED_TIMELINE_ITEM_TYPES and duration <= 0:
                invalid_items.append({"item_type": item_type, "duration_minutes": duration})
            elif item_type == "buffer" and duration < 0:
                invalid_items.append({"item_type": item_type, "duration_minutes": duration})
            elif item_type not in self._REQUIRED_TIMELINE_ITEM_TYPES | {"buffer"} and duration <= 0:
                invalid_items.append({"item_type": item_type, "duration_minutes": duration})

        if invalid_items:
            return self._fail(
                "timeline_duration",
                "Draft timeline contains invalid item durations.",
                draft_id=draft_id,
                details={"invalid_items": invalid_items, "durations": durations},
            )

        total_duration = sum(durations)
        min_minutes, max_minutes = self._duration_bounds_minutes(plan)
        details = {
            "total_duration_minutes": total_duration,
            "min_duration_minutes": min_minutes,
            "max_duration_minutes": max_minutes,
        }
        if min_minutes <= total_duration <= max_minutes:
            return self._pass(
                "timeline_duration",
                "Draft timeline duration fits the requested range.",
                draft_id=draft_id,
                details=details,
            )
        return self._warn(
            "timeline_duration",
            "Draft timeline duration is outside the requested range.",
            draft_id=draft_id,
            details=details,
        )

    def _check_child_friendly_constraint(
        self,
        plan: QueryPlan,
        draft: ItineraryDraft,
        draft_id: str,
        indexes: dict[str, Any],
    ) -> ReviewCheck:
        if not plan.intent.constraints.child_friendly:
            return self._pass(
                "child_friendly_constraint",
                "Child-friendly constraint is not requested.",
                draft_id=draft_id,
                details={"requested": False},
            )

        activity_id = self._activity_id(draft)
        dining_id = self._dining_id(draft)
        activity_has_evidence = self._has_marker(
            indexes["activity_by_id"].get(activity_id),
            getattr(draft, "activity", None),
            "child_friendly",
        )
        dining_has_evidence = self._has_marker(
            indexes["dining_by_id"].get(dining_id),
            getattr(draft, "dining", None),
            "child_friendly",
        )
        details = {
            "requested": True,
            "activity_has_child_friendly_evidence": activity_has_evidence,
            "dining_has_child_friendly_evidence": dining_has_evidence,
        }
        if activity_has_evidence and dining_has_evidence:
            return self._pass(
                "child_friendly_constraint",
                "Child-friendly evidence is present for activity and dining candidates.",
                draft_id=draft_id,
                details=details,
            )
        return self._warn(
            "child_friendly_constraint",
            "Child-friendly intent is present but candidate evidence is weak or missing.",
            draft_id=draft_id,
            details=details,
        )

    def _check_dining_preference_constraint(
        self,
        plan: QueryPlan,
        draft: ItineraryDraft,
        draft_id: str,
        indexes: dict[str, Any],
    ) -> ReviewCheck:
        requested = "lighter_options" in plan.intent.dining_preferences
        if not requested:
            return self._pass(
                "dining_preference_constraint",
                "Light dining preference is not requested.",
                draft_id=draft_id,
                details={"requested": False},
            )

        dining_id = self._dining_id(draft)
        dining_has_evidence = self._has_marker(
            indexes["dining_by_id"].get(dining_id),
            getattr(draft, "dining", None),
            "lighter_options",
        )
        details = {
            "requested": True,
            "dining_has_lighter_options_evidence": dining_has_evidence,
        }
        if dining_has_evidence:
            return self._pass(
                "dining_preference_constraint",
                "Light dining evidence is present for the dining candidate.",
                draft_id=draft_id,
                details=details,
            )
        return self._warn(
            "dining_preference_constraint",
            "Light dining preference is present but dining evidence is weak or missing.",
            draft_id=draft_id,
            details=details,
        )

    def _check_distance_constraint(
        self,
        plan: QueryPlan,
        draft: ItineraryDraft,
        draft_id: str,
    ) -> ReviewCheck:
        max_distance_km = plan.intent.constraints.max_distance_km
        route = getattr(draft, "route", None)
        distance_meters = getattr(route, "distance_meters", None) if route is not None else None
        details = {
            "max_distance_km": max_distance_km,
            "route_distance_meters": distance_meters,
        }
        if max_distance_km is None:
            return self._pass(
                "distance_constraint",
                "No maximum distance constraint is requested.",
                draft_id=draft_id,
                details=details,
            )
        if not isinstance(distance_meters, int):
            return self._pass(
                "distance_constraint",
                "Route distance is unavailable, so maximum distance cannot be evaluated here.",
                draft_id=draft_id,
                details=details,
            )
        if distance_meters > max_distance_km * 1000:
            return self._warn(
                "distance_constraint",
                "Route distance exceeds the requested maximum distance.",
                draft_id=draft_id,
                details=details,
            )
        return self._pass(
            "distance_constraint",
            "Route distance fits the requested maximum distance.",
            draft_id=draft_id,
            details=details,
        )

    def _check_actions_require_confirmation(self, draft: ItineraryDraft, draft_id: str) -> ReviewCheck:
        actions = self._actions(draft)
        if not actions:
            return self._warn(
                "actions_require_confirmation",
                "Draft does not propose any confirmation-gated actions.",
                draft_id=draft_id,
                details={"action_count": 0},
            )
        invalid_actions = [
            self._action_summary(action)
            for action in actions
            if getattr(action, "requires_confirmation", None) is not True
        ]
        if invalid_actions:
            return self._fail(
                "actions_require_confirmation",
                "One or more proposed actions do not require user confirmation.",
                draft_id=draft_id,
                details={"invalid_actions": invalid_actions},
            )
        return self._pass(
            "actions_require_confirmation",
            "All proposed actions require user confirmation.",
            draft_id=draft_id,
            details={"action_count": len(actions)},
        )

    def _check_actions_reference_draft_objects(
        self,
        draft: ItineraryDraft,
        draft_id: str,
        indexes: dict[str, Any],
    ) -> ReviewCheck:
        actions = self._actions(draft)
        activity_id = self._activity_id(draft)
        dining_id = self._dining_id(draft)
        queue_targets = {dining_id} if dining_id else set()
        queue_id = indexes["queue_ids_by_dining_id"].get(dining_id)
        if queue_id:
            queue_targets.add(queue_id)
        draft_queue_id = self._draft_queue_id(draft)
        if draft_queue_id:
            queue_targets.add(draft_queue_id)
        selected_addon = self._selected_addon(draft)

        invalid_actions = []
        for action in actions:
            action_type = getattr(action, "action_type", None)
            target_id = getattr(action, "target_id", None)
            if action_type == "book_ticket" and target_id == activity_id:
                continue
            if action_type == "reserve_restaurant" and target_id == dining_id:
                continue
            if action_type == "join_queue" and target_id in queue_targets:
                continue
            if action_type == "order_addon" and self._order_addon_is_valid(
                action,
                dining_id,
                selected_addon,
                indexes,
            ):
                continue
            if action_type == "send_message" and self._send_message_is_valid(action, draft):
                continue
            invalid_actions.append(self._action_summary(action))

        if invalid_actions:
            return self._fail(
                "actions_reference_draft_objects",
                "One or more proposed actions target objects outside the selected draft evidence.",
                draft_id=draft_id,
                details={
                    "activity_id": activity_id,
                    "dining_id": dining_id,
                    "selected_addon_id": selected_addon.get("candidate_id"),
                    "queue_targets": sorted(target for target in queue_targets if target),
                    "invalid_actions": invalid_actions,
                },
            )
        return self._pass(
            "actions_reference_draft_objects",
            "Proposed actions target selected draft objects.",
            draft_id=draft_id,
            details={
                "activity_id": activity_id,
                "dining_id": dining_id,
                "selected_addon_id": selected_addon.get("candidate_id"),
                "queue_targets": sorted(target for target in queue_targets if target),
                "action_count": len(actions),
            },
        )

    def _check_actions_have_no_execution_fields(
        self,
        draft: ItineraryDraft,
        draft_id: str,
    ) -> ReviewCheck:
        invalid_actions = []
        for action in self._actions(draft):
            forbidden_keys = self._find_forbidden_exact_keys(
                self._jsonable(action),
                self._EXECUTION_FIELD_KEYS,
            )
            if forbidden_keys:
                invalid_actions.append(
                    {
                        **self._action_summary(action),
                        "forbidden_keys": forbidden_keys,
                    }
                )
        if invalid_actions:
            return self._fail(
                "actions_have_no_execution_fields",
                "Proposed actions include durable execution fields before confirmation.",
                draft_id=draft_id,
                details={"invalid_actions": invalid_actions},
            )
        return self._pass(
            "actions_have_no_execution_fields",
            "Proposed actions do not contain durable execution fields.",
            draft_id=draft_id,
        )

    def _check_sensitive_payload_scan(self, draft: ItineraryDraft, draft_id: str) -> ReviewCheck:
        matched_keys = self._find_sensitive_keys(self._jsonable(draft))
        if matched_keys:
            return self._fail(
                "sensitive_payload_scan",
                "Draft payload contains sensitive, debug, or internal key names.",
                draft_id=draft_id,
                details={"matched_keys": matched_keys},
            )
        return self._pass(
            "sensitive_payload_scan",
            "Draft payload does not contain sensitive, debug, or internal key names.",
            draft_id=draft_id,
        )

    def _duration_bounds_minutes(self, plan: QueryPlan) -> tuple[int, int]:
        time_window = plan.intent.time_window
        if (
            time_window.duration_hours_min is not None
            and time_window.duration_hours_max is not None
        ):
            return time_window.duration_hours_min * 60, time_window.duration_hours_max * 60
        return self._DEFAULT_MIN_DURATION_MINUTES, self._DEFAULT_MAX_DURATION_MINUTES

    def _has_marker(
        self,
        enriched: EnrichedCandidate | None,
        candidate_ref: Any,
        marker: str,
    ) -> bool:
        if self._sequence_has_marker(getattr(candidate_ref, "tags", None), marker):
            return True
        if self._mapping_has_marker(getattr(candidate_ref, "evidence", None), marker):
            return True
        if enriched is None:
            return False
        if self._sequence_has_marker(enriched.candidate.tags, marker):
            return True
        return any(
            self._mapping_has_marker(value, marker)
            for value in (
                enriched.poi_detail,
                enriched.opening_hours,
                enriched.queue,
                enriched.table_availability,
                enriched.ticket_availability,
            )
        )

    def _sequence_has_marker(self, value: Any, marker: str) -> bool:
        if not isinstance(value, list):
            return False
        return any(self._text_matches_marker(item, marker) for item in value)

    def _mapping_has_marker(self, value: Any, marker: str) -> bool:
        if isinstance(value, dict):
            return any(
                self._text_matches_marker(key, marker) or self._mapping_has_marker(child, marker)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(self._mapping_has_marker(item, marker) for item in value)
        return self._text_matches_marker(value, marker)

    def _text_matches_marker(self, value: Any, marker: str) -> bool:
        if not isinstance(value, str):
            return False
        normalized = value.casefold().replace("-", "_").replace(" ", "_")
        return marker.casefold() in normalized

    def _find_sensitive_keys(self, value: Any) -> list[str]:
        matches = []
        for key in self._walk_keys(value):
            normalized_key = key.casefold()
            if any(fragment in normalized_key for fragment in self._SENSITIVE_KEY_FRAGMENTS):
                matches.append(key)
        return sorted(set(matches))

    def _find_forbidden_exact_keys(self, value: Any, forbidden_keys: set[str]) -> list[str]:
        return sorted(
            {
                key
                for key in self._walk_keys(value)
                if key.casefold() in forbidden_keys
            }
        )

    def _walk_keys(self, value: Any) -> list[str]:
        if isinstance(value, dict):
            keys = []
            for key, child in value.items():
                if isinstance(key, str):
                    keys.append(key)
                keys.extend(self._walk_keys(child))
            return keys
        if isinstance(value, list):
            keys = []
            for item in value:
                keys.extend(self._walk_keys(item))
            return keys
        return []

    def _jsonable(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: self._jsonable(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        return value

    def _draft_queue_id(self, draft: ItineraryDraft) -> str | None:
        dining = getattr(draft, "dining", None)
        evidence = getattr(dining, "evidence", None)
        if not isinstance(evidence, dict):
            return None
        queue = evidence.get("queue")
        if isinstance(queue, dict) and isinstance(queue.get("queue_id"), str):
            return queue["queue_id"]
        return None

    def _selected_addon(self, draft: ItineraryDraft) -> dict[str, Any]:
        evidence = getattr(draft, "evidence", None)
        if not isinstance(evidence, dict):
            return {}
        selected_addon = evidence.get("selected_addon")
        return selected_addon if isinstance(selected_addon, dict) else {}

    def _order_addon_is_valid(
        self,
        action: Any,
        dining_id: str | None,
        selected_addon: dict[str, Any],
        indexes: dict[str, Any],
    ) -> bool:
        target_id = getattr(action, "target_id", None)
        if not isinstance(target_id, str) or not target_id:
            return False
        if dining_id is None:
            return False
        if target_id not in indexes["addon_ids"]:
            return False
        if self._text_or_none(selected_addon.get("candidate_id")) != target_id:
            return False

        payload = getattr(action, "payload", None)
        if not isinstance(payload, dict):
            return False
        if self._text_or_none(payload.get("vendor_id")) != target_id:
            return False

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return False
        for item in items:
            if not isinstance(item, dict):
                return False
            if self._text_or_none(item.get("sku")) is None:
                return False
            if self._positive_int(item.get("quantity")) is None:
                return False

        route_key = self._route_key(selected_addon.get("route_key"))
        if route_key is None:
            route_key = (dining_id, target_id)
        if route_key != (dining_id, target_id):
            return False
        if route_key not in indexes["route_keys"]:
            return False
        return True

    def _send_message_is_valid(self, action: Any, draft: ItineraryDraft) -> bool:
        evidence = self._post_confirmation_message(draft)
        recipient = self._text_or_none(evidence.get("recipient"))
        if recipient is None:
            return False

        target_id = getattr(action, "target_id", None)
        if target_id != recipient:
            return False

        payload = getattr(action, "payload", None)
        if not isinstance(payload, dict):
            return False
        if self._text_or_none(payload.get("recipient")) != recipient:
            return False
        if self._text_or_none(payload.get("message")) is None:
            return False
        return True

    def _post_confirmation_message(self, draft: ItineraryDraft) -> dict[str, Any]:
        evidence = getattr(draft, "evidence", None)
        if not isinstance(evidence, dict):
            return {}
        message = evidence.get("post_confirmation_message")
        return message if isinstance(message, dict) else {}

    def _actions(self, draft: ItineraryDraft) -> list[Any]:
        actions = getattr(draft, "proposed_actions", None)
        return actions if isinstance(actions, list) else []

    def _activity_id(self, draft: ItineraryDraft) -> str | None:
        return self._candidate_id(getattr(draft, "activity", None))

    def _dining_id(self, draft: ItineraryDraft) -> str | None:
        return self._candidate_id(getattr(draft, "dining", None))

    def _candidate_id(self, candidate_ref: Any) -> str | None:
        candidate_id = getattr(candidate_ref, "candidate_id", None)
        return candidate_id if isinstance(candidate_id, str) and candidate_id else None

    def _route_key(self, value: Any) -> tuple[str, str] | None:
        if not isinstance(value, list) or len(value) != 2:
            return None
        origin_id = self._text_or_none(value[0])
        destination_id = self._text_or_none(value[1])
        if origin_id is None or destination_id is None:
            return None
        return origin_id, destination_id

    def _text_or_none(self, value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    def _positive_int(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value > 0:
            return value
        return None

    def _draft_id(self, draft: ItineraryDraft) -> str:
        draft_id = getattr(draft, "draft_id", None)
        return draft_id if isinstance(draft_id, str) and draft_id else "<unknown>"

    def _action_summary(self, action: Any) -> dict[str, Any]:
        return {
            "action_ref": getattr(action, "action_ref", None),
            "action_type": getattr(action, "action_type", None),
            "target_id": getattr(action, "target_id", None),
        }

    def _pass(
        self,
        check_name: str,
        message: str,
        *,
        draft_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> ReviewCheck:
        return ReviewCheck(
            check_name=check_name,
            status="passed",
            severity="info",
            message=message,
            draft_id=draft_id,
            details=details or {},
        )

    def _warn(
        self,
        check_name: str,
        message: str,
        *,
        draft_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> ReviewCheck:
        return ReviewCheck(
            check_name=check_name,
            status="warning",
            severity="warning",
            message=message,
            draft_id=draft_id,
            details=details or {},
        )

    def _fail(
        self,
        check_name: str,
        message: str,
        *,
        draft_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> ReviewCheck:
        return ReviewCheck(
            check_name=check_name,
            status="failed",
            severity="error",
            message=message,
            draft_id=draft_id,
            details=details or {},
        )
