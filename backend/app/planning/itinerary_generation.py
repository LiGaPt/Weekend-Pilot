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
from backend.app.planning.query_planner import intent_requests_addon
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


@dataclass(frozen=True)
class _SelectedAddon:
    candidate: EnrichedCandidate
    route: RouteMatrixEntry
    vendor_id: str
    sku: str


class DeterministicItineraryGenerator:
    generator_version = "deterministic_itinerary_generator_v1"
    _USABLE_ROUTE_STATUSES = {"succeeded", "cached"}
    _MIN_TOTAL_DURATION_MINUTES = 240
    _MAX_TOTAL_DURATION_MINUTES = 360
    _ACTIVITY_DURATION_MINUTES = 150
    _DEFAULT_TRANSFER_DURATION_MINUTES = 20
    _DINING_DURATION_MINUTES = 90
    _COPY_TEMPLATES = {
        "family": {
            "summary": "先去{activity}做亲子活动，再去{dining}吃清淡晚餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和票务信息安排亲子活动。",
            "dining_note": "结合清淡偏好、亲子友好度和桌位信息安排晚餐。",
            "reasons": ["已选择亲子活动", "已选择清淡用餐", "活动到餐厅路线已验证"],
        },
        "friends": {
            "summary": "先去{activity}和朋友散步聊天，再去{dining}吃适合分享的轻松晚餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和聚会氛围安排朋友同行活动。",
            "dining_note": "结合分享型用餐、朋友聚会氛围和桌位信息安排晚餐。",
            "reasons": ["已选择适合朋友聚会的活动", "已选择适合分享的用餐", "活动到餐厅路线已验证"],
        },
        "solo": {
            "summary": "先去{activity}一个人轻松逛逛，再去{dining}吃一顿简餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和轻松节奏安排单人活动。",
            "dining_note": "结合简餐偏好、安静程度和桌位信息安排用餐。",
            "reasons": ["已选择适合单人放松的活动", "已选择轻量简餐", "活动到餐厅路线已验证"],
        },
        "couple": {
            "summary": "先去{activity}和伴侣慢慢逛，再去{dining}吃一顿轻松晚餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和两人同行节奏安排活动。",
            "dining_note": "结合约会氛围、轻食偏好和桌位信息安排晚餐。",
            "reasons": ["已选择适合两人同行的活动", "已选择适合约会节奏的用餐", "活动到餐厅路线已验证"],
        },
        "rainy": {
            "summary": "先去{activity}安排室内避雨活动，再去{dining}吃一顿热一点的简餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和室内可行性安排雨天活动。",
            "dining_note": "结合热食偏好、就近便利度和桌位信息安排雨天用餐。",
            "reasons": ["已选择雨天可行的室内活动", "已选择适合雨天的热食简餐", "活动到餐厅路线已验证"],
        },
        "budget": {
            "summary": "先去{activity}安排低预算活动，再去{dining}吃一顿平价简餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和价格友好度安排低预算活动。",
            "dining_note": "结合预算限制、出餐效率和桌位信息安排平价用餐。",
            "reasons": ["已选择免费或低价活动", "已选择预算友好的用餐", "活动到餐厅路线已验证"],
        },
        "generic": {
            "summary": "先去{activity}安排活动，再去{dining}用餐，{route_text}。",
            "activity_note": "根据候选详情、营业时间和可用性安排活动。",
            "dining_note": "结合用餐偏好和桌位信息安排用餐。",
            "reasons": ["已选择可行活动", "已选择可行用餐", "活动到餐厅路线已验证"],
        },
    }

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
                    "缺少可用于生成行程的活动候选。",
                )
            )
        if not enrichment.enriched_dining_candidates:
            result.failed_reasons.append(
                self._failure(
                    "missing_dining_candidate",
                    "缺少可用于生成行程的用餐候选。",
                )
            )
        if result.failed_reasons:
            return result

        pairs = self._build_ordered_pairs(enrichment)
        if not pairs:
            result.failed_reasons.append(
                self._failure(
                    "missing_usable_route",
                    "没有可用于串联活动和用餐地点的路线。",
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
        copy_profile = self._display_copy_profile(plan, pair)
        copy = self._COPY_TEMPLATES[copy_profile]
        timeline = self._build_timeline(plan, pair, warnings, copy)
        total_duration = sum(item.duration_minutes for item in timeline)
        proposed_actions, addon_evidence = self._build_proposed_actions(plan, enrichment, pair, draft_id)
        route_ref = self._route_ref(pair.route)
        evidence = {
            "parser_version": plan.intent.parser_version,
            "planner_version": plan.planner_version,
            "enricher_version": enrichment.enricher_version,
            "generator_version": self.generator_version,
            "activity_candidate_id": pair.activity.candidate.candidate_id,
            "dining_candidate_id": pair.dining.candidate.candidate_id,
            "route_tool_event_id": pair.route.tool_event_id,
            "provider_profile": enrichment.provider_profile,
        }
        if addon_evidence is not None:
            evidence["selected_addon"] = addon_evidence

        return ItineraryDraft(
            draft_id=draft_id,
            title=f"{pair.activity.candidate.name} + {pair.dining.candidate.name}",
            summary=self._summary(pair, copy),
            activity=self._candidate_ref(pair.activity),
            dining=self._candidate_ref(pair.dining),
            route=route_ref,
            timeline=timeline,
            proposed_actions=proposed_actions,
            feasibility=FeasibilitySummary(
                is_feasible=True,
                reasons=list(copy["reasons"]),
                warnings=warnings,
                total_duration_minutes=total_duration,
                route_duration_minutes=pair.route.duration_minutes,
                queue_wait_minutes=self._queue_wait_minutes(pair.dining),
            ),
            evidence=evidence,
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
        copy: dict[str, Any],
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
                f"体验{pair.activity.candidate.name}",
                pair.activity.candidate.candidate_id,
                self._ACTIVITY_DURATION_MINUTES,
                [str(copy["activity_note"])],
            ),
            (
                "transfer",
                f"前往{pair.dining.candidate.name}",
                None,
                transfer_duration,
                ["已验证活动地点到餐厅的路线和预计耗时。"],
            ),
            (
                "dining",
                f"在{pair.dining.candidate.name}用餐",
                pair.dining.candidate.candidate_id,
                self._DINING_DURATION_MINUTES,
                [str(copy["dining_note"])],
            ),
            (
                "buffer",
                "缓冲和返程准备",
                None,
                buffer_duration,
                ["预留缓冲时间，方便补水、整理物品和准备返程。"],
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
            self._append_warning(warnings, "行程可能超过用户给定时间窗")
        return timeline

    def _build_proposed_actions(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        pair: _DraftPair,
        draft_id: str,
    ) -> tuple[list[ProposedAction], dict[str, Any] | None]:
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
                    "票务可用，确认后可提前锁定入场名额。",
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
                    "餐厅有可订桌位，确认后可提前锁定晚餐座位。",
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
                    "当前可排队取号，且没有可用订座操作。",
                )
            )

        selected_addon = self._select_addon(plan, enrichment, pair)
        if selected_addon is not None:
            actions.append(
                self._action(
                    draft_id,
                    len(actions) + 1,
                    "order_addon",
                    selected_addon.candidate.candidate.candidate_id,
                    {
                        "vendor_id": selected_addon.vendor_id,
                        "items": [{"sku": selected_addon.sku, "quantity": party_size}],
                    },
                    "补给点可顺路到达，确认后可提前下单补水或小食。",
                )
            )
            return actions, {
                "candidate_id": selected_addon.candidate.candidate.candidate_id,
                "name": selected_addon.candidate.candidate.name,
                "route_key": [
                    selected_addon.route.origin_candidate_id,
                    selected_addon.route.destination_candidate_id,
                ],
                "route_tool_event_id": selected_addon.route.tool_event_id,
            }

        return actions, None

    def _select_addon(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        pair: _DraftPair,
    ) -> _SelectedAddon | None:
        if not intent_requests_addon(plan.intent):
            return None

        dining_candidate_id = pair.dining.candidate.candidate_id
        for addon in enrichment.enriched_other_candidates:
            if addon.candidate.category != "addon":
                continue
            if not self._addon_is_open(addon):
                continue
            poi_detail = addon.poi_detail if isinstance(addon.poi_detail, dict) else None
            if poi_detail is None:
                continue
            vendor_id = self._text_or_none(poi_detail.get("vendor_id"))
            if vendor_id != addon.candidate.candidate_id:
                continue
            sku = self._water_sku(poi_detail.get("menu"))
            if sku is None:
                continue
            route = self._find_route(
                enrichment,
                dining_candidate_id,
                addon.candidate.candidate_id,
            )
            if route is None:
                continue
            return _SelectedAddon(
                candidate=addon,
                route=route,
                vendor_id=vendor_id,
                sku=sku,
            )
        return None

    def _addon_is_open(self, addon: EnrichedCandidate) -> bool:
        return isinstance(addon.opening_hours, dict) and addon.opening_hours.get("is_open") is True

    def _water_sku(self, menu: Any) -> str | None:
        if not isinstance(menu, list):
            return None
        for item in menu:
            if not isinstance(item, dict):
                continue
            sku = self._text_or_none(item.get("sku"))
            if sku == "water":
                return sku
        return None

    def _find_route(
        self,
        enrichment: CandidateEnrichmentResult,
        origin_candidate_id: str,
        destination_candidate_id: str,
    ) -> RouteMatrixEntry | None:
        for route in enrichment.route_matrix:
            if route.status not in self._USABLE_ROUTE_STATUSES:
                continue
            if route.origin_candidate_id != origin_candidate_id:
                continue
            if route.destination_candidate_id != destination_candidate_id:
                continue
            return route
        return None

    def _warnings_for_pair(self, plan: QueryPlan, pair: _DraftPair) -> list[str]:
        del plan
        warnings = []
        if not self._has_available_ticket_evidence(pair.activity):
            self._append_warning(warnings, "活动票务信息不完整")
        if self._dining_availability_rank(pair.dining) == 2:
            self._append_warning(warnings, "餐厅桌位或排队信息不完整")
        queue_wait = self._queue_wait_minutes(pair.dining)
        if queue_wait is not None and queue_wait > 30:
            self._append_warning(warnings, "餐厅排队等待较长")
        return warnings

    def _summary(self, pair: _DraftPair, copy: dict[str, Any]) -> str:
        if pair.route.duration_minutes is None:
            route_text = "路线已验证"
        else:
            route_text = f"中间步行约{pair.route.duration_minutes}分钟"
        return str(copy["summary"]).format(
            activity=pair.activity.candidate.name,
            dining=pair.dining.candidate.name,
            route_text=route_text,
        )

    def _display_copy_profile(self, plan: QueryPlan, pair: _DraftPair) -> str:
        intent = plan.intent
        raw_text = intent.raw_text.lower()
        activity_tags = {tag.lower() for tag in pair.activity.candidate.tags}
        dining_tags = {tag.lower() for tag in pair.dining.candidate.tags}
        pair_tags = activity_tags | dining_tags
        has_child_signal = bool(intent.participants.children_ages) or intent.constraints.child_friendly

        if has_child_signal:
            return "family"
        if any(keyword in raw_text for keyword in ("雨", "下雨", "rain", "rainy")) or pair_tags.intersection(
            {"comfort_food", "warm_food", "market", "nearby"}
        ):
            return "rainy"
        if any(keyword in raw_text for keyword in ("预算", "便宜", "低价", "免费", "budget", "cheap", "free")) or pair_tags.intersection(
            {"budget_limited", "free_activity", "value_set"}
        ):
            return "budget"
        if intent.scenario_type == "friends":
            return "friends"
        if (
            not has_child_signal
            and intent.participants.adults >= 2
            and (
                any(keyword in raw_text for keyword in ("伴侣", "爱人", "另一半", "wife", "husband", "partner"))
                or pair_tags.intersection({"date_friendly", "couple_friendly", "gallery", "citywalk"})
            )
        ):
            return "couple"
        if intent.scenario_type == "solo" or (not has_child_signal and intent.participants.adults == 1):
            return "solo"
        return "generic"

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
