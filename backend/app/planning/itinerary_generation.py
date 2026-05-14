from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from backend.app.planning.enriched_candidates import (
    CandidateEnrichmentResult,
    EnrichedCandidate,
    RouteMatrixEntry,
)
from backend.app.planning.itinerary_drafts import (
    FeasibilitySummary,
    ItineraryCandidateRef,
    ItineraryDraft,
    ItineraryDraftResult,
    ItineraryFailureReason,
    ItineraryRouteRef,
    ProposedAction,
    TimelineItem,
)
from backend.app.planning.schemas import QueryPlan


@dataclass(frozen=True)
class _DraftPair:
    activity: EnrichedCandidate
    dining: EnrichedCandidate
    route: RouteMatrixEntry
    activity_index: int
    dining_index: int


class DeterministicItineraryGenerator:
    generator_version = "deterministic_itinerary_generator_v1"
    _USABLE_ROUTE_STATUSES = {"succeeded", "cached"}
    _MIN_TOTAL_DURATION_MINUTES = 240
    _MAX_TOTAL_DURATION_MINUTES = 360
    _ACTIVITY_DURATION_MINUTES = 150
    _DEFAULT_TRANSFER_DURATION_MINUTES = 20
    _DINING_DURATION_MINUTES = 90

    def __init__(self, max_drafts: int = 3) -> None:
        self._max_drafts = max(0, max_drafts)

    def generate(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
    ) -> ItineraryDraftResult:
        result = ItineraryDraftResult(
            run_id=enrichment.run_id,
            provider_profile=enrichment.provider_profile,
            generator_version=self.generator_version,
        )

        if not enrichment.enriched_activity_candidates:
            result.failed_reasons.append(
                self._failure(
                    "missing_activity_candidate",
                    "No enriched activity candidates are available for itinerary generation.",
                )
            )
        if not enrichment.enriched_dining_candidates:
            result.failed_reasons.append(
                self._failure(
                    "missing_dining_candidate",
                    "No enriched dining candidates are available for itinerary generation.",
                )
            )
        if result.failed_reasons:
            return result

        pairs = self._build_ordered_pairs(enrichment)
        if not pairs:
            result.failed_reasons.append(
                self._failure(
                    "missing_usable_route",
                    "No usable activity-to-dining route is available for itinerary generation.",
                    {
                        "route_count": len(enrichment.route_matrix),
                        "usable_route_statuses": sorted(self._USABLE_ROUTE_STATUSES),
                    },
                )
            )
            return result

        for draft_index, pair in enumerate(pairs[: self._max_drafts], start=1):
            result.drafts.append(self._build_draft(plan, enrichment, pair, draft_index))

        return result

    def _build_ordered_pairs(self, enrichment: CandidateEnrichmentResult) -> list[_DraftPair]:
        activity_by_id = {
            item.candidate.candidate_id: item
            for item in enrichment.enriched_activity_candidates
            if self._activity_is_usable(item)
        }
        dining_by_id = {
            item.candidate.candidate_id: item
            for item in enrichment.enriched_dining_candidates
            if self._dining_is_usable(item)
        }
        activity_index = {
            item.candidate.candidate_id: index
            for index, item in enumerate(enrichment.enriched_activity_candidates)
        }
        dining_index = {
            item.candidate.candidate_id: index
            for index, item in enumerate(enrichment.enriched_dining_candidates)
        }

        pairs = []
        for route in enrichment.route_matrix:
            if route.status not in self._USABLE_ROUTE_STATUSES:
                continue
            activity = activity_by_id.get(route.origin_candidate_id)
            dining = dining_by_id.get(route.destination_candidate_id)
            if activity is None or dining is None:
                continue
            pairs.append(
                _DraftPair(
                    activity=activity,
                    dining=dining,
                    route=route,
                    activity_index=activity_index[route.origin_candidate_id],
                    dining_index=dining_index[route.destination_candidate_id],
                )
            )

        pairs.sort(key=self._pair_sort_key)
        return pairs

    def _pair_sort_key(self, pair: _DraftPair) -> tuple[Any, ...]:
        return (
            0,
            self._activity_ticket_rank(pair.activity),
            self._dining_availability_rank(pair.dining),
            self._known_int_sort(self._queue_wait_minutes(pair.dining)),
            self._known_int_sort(pair.route.duration_minutes),
            self._known_int_sort(pair.route.distance_meters),
            pair.activity_index,
            pair.dining_index,
        )

    def _build_draft(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        pair: _DraftPair,
        draft_index: int,
    ) -> ItineraryDraft:
        draft_id = f"draft_{draft_index}"
        warnings = self._warnings_for_pair(plan, pair)
        timeline = self._build_timeline(plan, pair, warnings)
        total_duration = sum(item.duration_minutes for item in timeline)
        proposed_actions = self._build_proposed_actions(plan, pair, draft_id)
        route_ref = self._route_ref(pair.route)

        return ItineraryDraft(
            draft_id=draft_id,
            title=f"{pair.activity.candidate.name} + {pair.dining.candidate.name}",
            summary=self._summary(pair),
            activity=self._candidate_ref(pair.activity),
            dining=self._candidate_ref(pair.dining),
            route=route_ref,
            timeline=timeline,
            proposed_actions=proposed_actions,
            feasibility=FeasibilitySummary(
                is_feasible=True,
                reasons=["activity_selected", "dining_selected", "route_verified"],
                warnings=warnings,
                total_duration_minutes=total_duration,
                route_duration_minutes=pair.route.duration_minutes,
                queue_wait_minutes=self._queue_wait_minutes(pair.dining),
            ),
            evidence={
                "parser_version": plan.intent.parser_version,
                "planner_version": plan.planner_version,
                "enricher_version": enrichment.enricher_version,
                "generator_version": self.generator_version,
                "activity_candidate_id": pair.activity.candidate.candidate_id,
                "dining_candidate_id": pair.dining.candidate.candidate_id,
                "route_tool_event_id": pair.route.tool_event_id,
                "provider_profile": enrichment.provider_profile,
            },
        )

    def _candidate_ref(self, enriched: EnrichedCandidate) -> ItineraryCandidateRef:
        evidence = {}
        for key in (
            "poi_detail",
            "opening_hours",
            "queue",
            "table_availability",
            "ticket_availability",
        ):
            value = getattr(enriched, key)
            if value is not None:
                evidence[key] = deepcopy(value)

        return ItineraryCandidateRef(
            candidate_id=enriched.candidate.candidate_id,
            name=enriched.candidate.name,
            category=enriched.candidate.category,
            provider=enriched.candidate.provider,
            address=enriched.candidate.address,
            tags=list(enriched.candidate.tags),
            tool_event_ids=self._enrichment_tool_event_ids(enriched),
            evidence=evidence,
        )

    def _route_ref(self, route: RouteMatrixEntry) -> ItineraryRouteRef:
        summary = None
        if isinstance(route.route_json, dict) and isinstance(route.route_json.get("summary"), str):
            summary = route.route_json["summary"]

        return ItineraryRouteRef(
            origin_candidate_id=route.origin_candidate_id,
            destination_candidate_id=route.destination_candidate_id,
            provider=route.provider,
            mode=route.mode,
            distance_meters=route.distance_meters,
            duration_minutes=route.duration_minutes,
            tool_event_id=route.tool_event_id,
            summary=summary,
        )

    def _build_timeline(
        self,
        plan: QueryPlan,
        pair: _DraftPair,
        warnings: list[str],
    ) -> list[TimelineItem]:
        transfer_duration = pair.route.duration_minutes or self._DEFAULT_TRANSFER_DURATION_MINUTES
        base_duration = (
            self._ACTIVITY_DURATION_MINUTES
            + transfer_duration
            + self._DINING_DURATION_MINUTES
        )
        buffer_duration = min(
            max(0, self._MIN_TOTAL_DURATION_MINUTES - base_duration),
            max(0, self._MAX_TOTAL_DURATION_MINUTES - base_duration),
        )
        start_at = self._timeline_start(plan)
        blocks = [
            (
                "activity",
                f"Visit {pair.activity.candidate.name}",
                pair.activity.candidate.candidate_id,
                self._ACTIVITY_DURATION_MINUTES,
                ["Activity block selected from enriched candidate evidence."],
            ),
            (
                "transfer",
                f"Transfer to {pair.dining.candidate.name}",
                None,
                transfer_duration,
                ["Route verified from activity to dining candidate."],
            ),
            (
                "dining",
                f"Dine at {pair.dining.candidate.name}",
                pair.dining.candidate.candidate_id,
                self._DINING_DURATION_MINUTES,
                ["Dining block selected from enriched candidate evidence."],
            ),
            (
                "buffer",
                "Buffer and wrap-up",
                None,
                buffer_duration,
                ["Keeps the draft within the MVP afternoon planning target."],
            ),
        ]

        timeline = []
        cursor = start_at
        for sequence, (item_type, title, candidate_id, duration, notes) in enumerate(blocks, start=1):
            end_at = cursor + timedelta(minutes=duration)
            timeline.append(
                TimelineItem(
                    sequence=sequence,
                    item_type=item_type,
                    title=title,
                    candidate_id=candidate_id,
                    duration_minutes=duration,
                    start_label=cursor.strftime("%H:%M"),
                    end_label=end_at.strftime("%H:%M"),
                    notes=notes,
                )
            )
            cursor = end_at

        requested_end = plan.intent.time_window.end_at
        if requested_end is not None and cursor > requested_end:
            self._append_warning(warnings, "timeline_exceeds_requested_window")
        return timeline

    def _build_proposed_actions(
        self,
        plan: QueryPlan,
        pair: _DraftPair,
        draft_id: str,
    ) -> list[ProposedAction]:
        actions = []
        party_size = self._party_size(plan)

        ticket = pair.activity.ticket_availability
        if isinstance(ticket, dict) and ticket.get("available") is True:
            payload = {
                "poi_id": self._text_or_default(
                    ticket.get("poi_id"),
                    pair.activity.candidate.candidate_id,
                ),
                "quantity": party_size,
            }
            time_slot = self._first_text(ticket.get("time_slots"))
            if time_slot is not None:
                payload["time_slot"] = time_slot
            actions.append(
                self._action(
                    draft_id,
                    len(actions) + 1,
                    "book_ticket",
                    pair.activity.candidate.candidate_id,
                    payload,
                    "Ticket availability is available.",
                )
            )

        table = pair.dining.table_availability
        has_reservation_action = False
        if isinstance(table, dict) and table.get("available") is True:
            payload = {
                "restaurant_id": self._text_or_default(
                    table.get("restaurant_id"),
                    pair.dining.candidate.candidate_id,
                ),
                "party_size": party_size,
            }
            time_slot = self._first_text(table.get("time_slots"))
            if time_slot is not None:
                payload["time_slot"] = time_slot
            actions.append(
                self._action(
                    draft_id,
                    len(actions) + 1,
                    "reserve_restaurant",
                    pair.dining.candidate.candidate_id,
                    payload,
                    "Table availability is available.",
                )
            )
            has_reservation_action = True

        queue = pair.dining.queue
        if (
            not has_reservation_action
            and isinstance(queue, dict)
            and queue.get("status") == "open"
        ):
            queue_id = self._text_or_none(queue.get("queue_id"))
            payload = {"party_size": party_size}
            if queue_id is not None:
                payload["queue_id"] = queue_id
            actions.append(
                self._action(
                    draft_id,
                    len(actions) + 1,
                    "join_queue",
                    queue_id or pair.dining.candidate.candidate_id,
                    payload,
                    "Queue is open and no table reservation action was selected.",
                )
            )

        return actions

    def _warnings_for_pair(self, plan: QueryPlan, pair: _DraftPair) -> list[str]:
        del plan
        warnings = []
        if not self._has_available_ticket_evidence(pair.activity):
            self._append_warning(warnings, "missing_ticket_availability")
        if self._dining_availability_rank(pair.dining) == 2:
            self._append_warning(warnings, "missing_table_or_queue_availability")
        queue_wait = self._queue_wait_minutes(pair.dining)
        if queue_wait is not None and queue_wait > 30:
            self._append_warning(warnings, "long_queue_wait")
        return warnings

    def _summary(self, pair: _DraftPair) -> str:
        if pair.route.duration_minutes is None:
            route_text = "with a verified transfer route"
        else:
            route_text = f"with a {pair.route.duration_minutes}-minute transfer"
        return (
            f"Visit {pair.activity.candidate.name}, then continue to "
            f"{pair.dining.candidate.name} {route_text}."
        )

    def _activity_is_usable(self, activity: EnrichedCandidate) -> bool:
        ticket = activity.ticket_availability
        if not isinstance(ticket, dict):
            return True
        return ticket.get("available") is not False

    def _dining_is_usable(self, dining: EnrichedCandidate) -> bool:
        table = dining.table_availability
        queue = dining.queue
        table_available = table.get("available") if isinstance(table, dict) else None
        queue_status = queue.get("status") if isinstance(queue, dict) else None

        if table_available is True or queue_status == "open":
            return True
        if table_available is False or queue_status is not None:
            return False
        return True

    def _activity_ticket_rank(self, activity: EnrichedCandidate) -> int:
        ticket = activity.ticket_availability
        if isinstance(ticket, dict) and ticket.get("available") is True:
            return 0
        if isinstance(ticket, dict) and ticket.get("available") is False:
            return 2
        return 1

    def _dining_availability_rank(self, dining: EnrichedCandidate) -> int:
        table = dining.table_availability
        if isinstance(table, dict) and table.get("available") is True:
            return 0
        queue = dining.queue
        if isinstance(queue, dict) and queue.get("status") == "open":
            return 1
        return 2

    def _has_available_ticket_evidence(self, activity: EnrichedCandidate) -> bool:
        ticket = activity.ticket_availability
        return isinstance(ticket, dict) and ticket.get("available") is True

    def _queue_wait_minutes(self, dining: EnrichedCandidate) -> int | None:
        queue = dining.queue
        if not isinstance(queue, dict):
            return None
        return self._int_or_none(queue.get("wait_minutes"))

    def _enrichment_tool_event_ids(self, enriched: EnrichedCandidate) -> list[Any]:
        event_ids = []
        seen = set()
        for result in enriched.tool_results + enriched.failed_tool_results:
            if result.tool_event_id is None or result.tool_event_id in seen:
                continue
            event_ids.append(result.tool_event_id)
            seen.add(result.tool_event_id)
        return event_ids

    def _timeline_start(self, plan: QueryPlan) -> datetime:
        start_at = plan.intent.time_window.start_at
        if start_at is not None:
            return start_at
        end_at = plan.intent.time_window.end_at
        if end_at is not None:
            return end_at.replace(hour=13, minute=30, second=0, microsecond=0)
        return datetime(2000, 1, 1, 13, 30)

    def _party_size(self, plan: QueryPlan) -> int:
        participants = plan.intent.participants
        return max(1, participants.adults + len(participants.children_ages))

    def _action(
        self,
        draft_id: str,
        action_index: int,
        action_type: str,
        target_id: str,
        payload: dict[str, Any],
        reason: str,
    ) -> ProposedAction:
        return ProposedAction(
            action_ref=f"{draft_id}_action_{action_index}",
            action_type=action_type,
            target_id=target_id,
            payload=payload,
            requires_confirmation=True,
            reason=reason,
        )

    def _failure(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ItineraryFailureReason:
        return ItineraryFailureReason(
            code=code,
            message=message,
            details=details or {},
        )

    def _known_int_sort(self, value: int | None) -> tuple[int, int]:
        if value is None:
            return (1, 0)
        return (0, value)

    def _append_warning(self, warnings: list[str], warning: str) -> None:
        if warning not in warnings:
            warnings.append(warning)

    def _first_text(self, value: Any) -> str | None:
        if not isinstance(value, list):
            return None
        for item in value:
            if isinstance(item, str) and item:
                return item
        return None

    def _text_or_default(self, value: Any, default: str) -> str:
        text = self._text_or_none(value)
        return text if text is not None else default

    def _text_or_none(self, value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    def _int_or_none(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None
