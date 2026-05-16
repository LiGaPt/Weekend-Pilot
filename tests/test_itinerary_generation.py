from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

from backend.app.planning import (
    Candidate,
    CandidateEnrichmentResult,
    DeterministicItineraryGenerator,
    EnrichedCandidate,
    EnrichmentToolResult,
    LocalLifeIntent,
    ParticipantProfile,
    QueryPlan,
    RouteMatrixEntry,
    TimeWindow,
)


def _intent(*, start_at: datetime | None = None, end_at: datetime | None = None) -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="family afternoon",
        participants=ParticipantProfile(adults=2, children_ages=[5]),
        time_window=TimeWindow(start_at=start_at, end_at=end_at),
        parser_version="test-parser",
    )


def _plan(*, start_at: datetime | None = None, end_at: datetime | None = None) -> QueryPlan:
    return QueryPlan(
        intent=_intent(start_at=start_at, end_at=end_at),
        provider_profile="mock_world",
        planner_version="test-planner",
    )


def _candidate(
    candidate_id: str,
    *,
    name: str | None = None,
    category: str = "activity",
    tags: list[str] | None = None,
    tool_event_id: UUID | None = None,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        name=name or candidate_id,
        category=category,
        provider="mock_world",
        address=f"{candidate_id} address",
        tags=tags or [],
        raw_payload={"poi_id": candidate_id},
        source_call_index=0,
        tool_event_id=tool_event_id,
    )


def _tool_result(
    tool_name: str,
    candidate_id: str,
    *,
    response_json: dict | None = None,
    tool_event_id: UUID | None = None,
) -> EnrichmentToolResult:
    return EnrichmentToolResult(
        stage="candidate_enrichment",
        candidate_id=candidate_id,
        tool_name=tool_name,
        provider="mock_world",
        status="succeeded",
        response_json=response_json or {},
        tool_event_id=tool_event_id or uuid4(),
    )


def _activity(
    candidate_id: str = "activity_museum_001",
    *,
    name: str = "徐汇亲子科学馆",
    ticket_available: bool | None = True,
    tool_event_ids: list[UUID] | None = None,
) -> EnrichedCandidate:
    candidate_event_id = uuid4()
    detail_event_id = (tool_event_ids or [uuid4()])[0]
    ticket = None
    if ticket_available is not None:
        ticket = {
            "poi_id": candidate_id,
            "available": ticket_available,
            "time_slots": ["13:30", "14:00"],
            "remaining": 20,
        }
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name=name,
            tags=["child_friendly", "indoor"],
            tool_event_id=candidate_event_id,
        ),
        poi_detail={"poi_id": candidate_id, "name": name},
        opening_hours={"is_open": True},
        ticket_availability=ticket,
        tool_results=[
            _tool_result(
                "get_poi_detail",
                candidate_id,
                response_json={"poi": {"poi_id": candidate_id}},
                tool_event_id=detail_event_id,
            )
        ],
    )


def _dining(
    candidate_id: str = "restaurant_light_001",
    *,
    name: str = "绿碗家庭轻食",
    table_available: bool | None = True,
    queue_status: str | None = "open",
    queue_wait_minutes: int | None = 10,
    tool_event_ids: list[UUID] | None = None,
) -> EnrichedCandidate:
    detail_event_id = (tool_event_ids or [uuid4()])[0]
    table = None
    if table_available is not None:
        table = {
            "restaurant_id": candidate_id,
            "available": table_available,
            "time_slots": ["17:30", "18:00"],
            "max_party_size": 4,
        }
    queue = None
    if queue_status is not None:
        queue = {
            "queue_id": f"queue_{candidate_id}",
            "poi_id": candidate_id,
            "status": queue_status,
            "wait_minutes": queue_wait_minutes,
        }
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name=name,
            category="dining",
            tags=["lighter_options", "child_friendly"],
        ),
        poi_detail={"poi_id": candidate_id, "name": name},
        opening_hours={"is_open": True},
        queue=queue,
        table_availability=table,
        tool_results=[
            _tool_result(
                "get_poi_detail",
                candidate_id,
                response_json={"poi": {"poi_id": candidate_id}},
                tool_event_id=detail_event_id,
            )
        ],
    )


def _route(
    origin_candidate_id: str = "activity_museum_001",
    destination_candidate_id: str = "restaurant_light_001",
    *,
    status: str = "succeeded",
    duration_minutes: int | None = 12,
    distance_meters: int | None = 850,
    tool_event_id: UUID | None = None,
) -> RouteMatrixEntry:
    return RouteMatrixEntry(
        origin_candidate_id=origin_candidate_id,
        destination_candidate_id=destination_candidate_id,
        provider="mock_world",
        mode="walking",
        status=status,
        route_json={"summary": "穿过安静街区的短途步行路线，适合推童车。"},
        distance_meters=distance_meters,
        duration_minutes=duration_minutes,
        tool_event_id=tool_event_id or uuid4(),
    )


def _enrichment(
    *,
    activities: list[EnrichedCandidate] | None = None,
    dining: list[EnrichedCandidate] | None = None,
    routes: list[RouteMatrixEntry] | None = None,
) -> CandidateEnrichmentResult:
    return CandidateEnrichmentResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        enriched_activity_candidates=[_activity()] if activities is None else activities,
        enriched_dining_candidates=[_dining()] if dining is None else dining,
        route_matrix=[_route()] if routes is None else routes,
        enricher_version="test-enricher",
    )


def test_generator_returns_failed_reason_when_activity_candidates_are_missing() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(),
        _enrichment(activities=[], dining=[_dining()], routes=[]),
    )

    assert result.drafts == []
    assert [reason.code for reason in result.failed_reasons] == ["missing_activity_candidate"]


def test_generator_returns_failed_reason_when_dining_candidates_are_missing() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(),
        _enrichment(activities=[_activity()], dining=[], routes=[]),
    )

    assert result.drafts == []
    assert [reason.code for reason in result.failed_reasons] == ["missing_dining_candidate"]


def test_generator_returns_failed_reason_when_usable_route_is_missing() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(),
        _enrichment(routes=[_route(status="failed")]),
    )

    assert result.drafts == []
    assert [reason.code for reason in result.failed_reasons] == ["missing_usable_route"]


def test_generator_creates_draft_with_refs_timeline_feasibility_and_actions() -> None:
    route_event_id = uuid4()
    activity_event_id = uuid4()
    dining_event_id = uuid4()
    enrichment = _enrichment(
        activities=[_activity(tool_event_ids=[activity_event_id])],
        dining=[_dining(tool_event_ids=[dining_event_id])],
        routes=[_route(tool_event_id=route_event_id)],
    )

    result = DeterministicItineraryGenerator().generate(_plan(), enrichment)

    assert result.run_id == enrichment.run_id
    assert result.provider_profile == "mock_world"
    assert result.generator_version == "deterministic_itinerary_generator_v1"
    assert len(result.drafts) == 1
    draft = result.drafts[0]
    assert draft.draft_id == "draft_1"
    assert draft.status == "draft"
    assert draft.activity.candidate_id == "activity_museum_001"
    assert draft.dining.candidate_id == "restaurant_light_001"
    assert activity_event_id in draft.activity.tool_event_ids
    assert dining_event_id in draft.dining.tool_event_ids
    assert draft.route is not None
    assert draft.route.tool_event_id == route_event_id
    assert draft.route.duration_minutes == 12
    assert draft.title == "徐汇亲子科学馆 + 绿碗家庭轻食"
    assert "清淡晚餐" in draft.summary
    assert [item.item_type for item in draft.timeline] == ["activity", "transfer", "dining", "buffer"]
    assert [item.title for item in draft.timeline] == [
        "体验徐汇亲子科学馆",
        "前往绿碗家庭轻食",
        "在绿碗家庭轻食用餐",
        "缓冲和返程准备",
    ]
    assert sum(item.duration_minutes for item in draft.timeline) == draft.feasibility.total_duration_minutes
    assert 240 <= draft.feasibility.total_duration_minutes <= 360
    assert draft.feasibility.is_feasible is True
    assert draft.feasibility.reasons == ["已选择亲子活动", "已选择清淡用餐", "活动到餐厅路线已验证"]
    assert [action.action_type for action in draft.proposed_actions] == [
        "book_ticket",
        "reserve_restaurant",
    ]
    assert draft.proposed_actions[0].reason == "票务可用，确认后可提前锁定入场名额。"
    assert draft.proposed_actions[1].reason == "餐厅有可订桌位，确认后可提前锁定晚餐座位。"
    assert all(action.requires_confirmation for action in draft.proposed_actions)
    assert "idempotency_key" not in draft.proposed_actions[0].payload
    assert draft.evidence["planner_version"] == "test-planner"
    assert draft.evidence["enricher_version"] == "test-enricher"


def test_timeline_uses_requested_start_label_and_warns_when_window_is_exceeded() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(
            start_at=datetime(2026, 5, 16, 15, 0),
            end_at=datetime(2026, 5, 16, 18, 0),
        ),
        _enrichment(),
    )

    draft = result.drafts[0]
    assert draft.timeline[0].start_label == "15:00"
    assert "行程可能超过用户给定时间窗" in draft.feasibility.warnings


def test_ticket_table_and_queue_actions_follow_availability_rules() -> None:
    queue_only = _dining(table_available=False, queue_status="open", queue_wait_minutes=8)

    result = DeterministicItineraryGenerator().generate(
        _plan(),
        _enrichment(dining=[queue_only]),
    )

    actions = result.drafts[0].proposed_actions
    assert [action.action_type for action in actions] == ["book_ticket", "join_queue"]
    assert actions[0].payload == {
        "poi_id": "activity_museum_001",
        "quantity": 3,
        "time_slot": "13:30",
    }
    assert actions[1].target_id == "queue_restaurant_light_001"
    assert actions[1].payload == {
        "queue_id": "queue_restaurant_light_001",
        "party_size": 3,
    }


def test_table_reservation_is_preferred_over_queue_action_when_both_are_available() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(),
        _enrichment(dining=[_dining(table_available=True, queue_status="open", queue_wait_minutes=5)]),
    )

    assert [action.action_type for action in result.drafts[0].proposed_actions] == [
        "book_ticket",
        "reserve_restaurant",
    ]


def test_route_duration_and_queue_wait_affect_deterministic_ordering() -> None:
    activity = _activity()
    short_route_dining = _dining("restaurant_short_route", name="Short Route Table", table_available=True)
    long_route_dining = _dining("restaurant_long_route", name="Long Route Table", table_available=True)
    low_queue_dining = _dining(
        "restaurant_low_queue",
        name="Low Queue",
        table_available=False,
        queue_wait_minutes=5,
    )
    high_queue_dining = _dining(
        "restaurant_high_queue",
        name="High Queue",
        table_available=False,
        queue_wait_minutes=25,
    )
    result = DeterministicItineraryGenerator(max_drafts=4).generate(
        _plan(),
        _enrichment(
            activities=[activity],
            dining=[long_route_dining, high_queue_dining, short_route_dining, low_queue_dining],
            routes=[
                _route(destination_candidate_id="restaurant_long_route", duration_minutes=30),
                _route(destination_candidate_id="restaurant_high_queue", duration_minutes=6),
                _route(destination_candidate_id="restaurant_short_route", duration_minutes=12),
                _route(destination_candidate_id="restaurant_low_queue", duration_minutes=20),
            ],
        ),
    )

    assert [draft.dining.candidate_id for draft in result.drafts] == [
        "restaurant_short_route",
        "restaurant_long_route",
        "restaurant_low_queue",
        "restaurant_high_queue",
    ]


def test_long_queue_wait_is_usable_but_warned_and_deprioritized() -> None:
    shorter_long_queue = _dining(
        "restaurant_long_queue",
        name="Long Queue",
        table_available=False,
        queue_wait_minutes=45,
    )
    longer_short_queue = _dining(
        "restaurant_short_queue",
        name="Short Queue",
        table_available=False,
        queue_wait_minutes=10,
    )

    result = DeterministicItineraryGenerator(max_drafts=2).generate(
        _plan(),
        _enrichment(
            dining=[shorter_long_queue, longer_short_queue],
            routes=[
                _route(destination_candidate_id="restaurant_long_queue", duration_minutes=5),
                _route(destination_candidate_id="restaurant_short_queue", duration_minutes=25),
            ],
        ),
    )

    assert [draft.dining.candidate_id for draft in result.drafts] == [
        "restaurant_short_queue",
        "restaurant_long_queue",
    ]
    assert "餐厅排队等待较长" in result.drafts[1].feasibility.warnings


def test_generator_preserves_route_and_enrichment_tool_event_ids() -> None:
    activity_event_id = uuid4()
    dining_event_id = uuid4()
    route_event_id = uuid4()

    result = DeterministicItineraryGenerator().generate(
        _plan(),
        _enrichment(
            activities=[_activity(tool_event_ids=[activity_event_id])],
            dining=[_dining(tool_event_ids=[dining_event_id])],
            routes=[_route(tool_event_id=route_event_id)],
        ),
    )

    draft = result.drafts[0]
    assert draft.activity.tool_event_ids == [activity_event_id]
    assert draft.dining.tool_event_ids == [dining_event_id]
    assert draft.route is not None
    assert draft.route.tool_event_id == route_event_id


def test_generator_does_not_mutate_input_enrichment_result() -> None:
    enrichment = _enrichment()
    before = deepcopy(enrichment.model_dump(mode="json"))

    DeterministicItineraryGenerator().generate(_plan(), enrichment)

    assert enrichment.model_dump(mode="json") == before
