from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from backend.app.planning import (
    Candidate,
    CandidateEnrichmentResult,
    DeterministicItineraryGenerator,
    EnrichedCandidate,
    EnrichmentToolResult,
    IntentConstraints,
    LocalLifeIntent,
    ParticipantProfile,
    QueryPlan,
    RouteMatrixEntry,
    TimeWindow,
)


def _intent(
    *,
    raw_text: str = "family afternoon",
    scenario_type: str = "family",
    adults: int = 2,
    children_ages: list[int] | None = None,
    child_friendly: bool = True,
    activity_preferences: list[str] | None = None,
    dining_preferences: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> LocalLifeIntent:
    resolved_children_ages = [5] if children_ages is None else children_ages
    return LocalLifeIntent(
        raw_text=raw_text,
        scenario_type=scenario_type,  # type: ignore[arg-type]
        participants=ParticipantProfile(adults=adults, children_ages=resolved_children_ages),
        time_window=TimeWindow(start_at=start_at, end_at=end_at),
        constraints=IntentConstraints(child_friendly=child_friendly),
        activity_preferences=activity_preferences or [],
        dining_preferences=dining_preferences or [],
        parser_version="test-parser",
    )


def _plan(**intent_kwargs) -> QueryPlan:
    return QueryPlan(
        intent=_intent(**intent_kwargs),
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
    tags: list[str] | None = None,
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
            tags=tags or ["child_friendly", "indoor"],
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
    tags: list[str] | None = None,
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
            tags=tags or ["lighter_options", "child_friendly"],
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


def _addon(
    candidate_id: str = "addon_drinks_001",
    *,
    name: str = "小水分补给站",
    menu: list[dict] | None = None,
    opening_is_open: bool = True,
) -> EnrichedCandidate:
    resolved_menu = [{"sku": "water", "name": "瓶装水", "price_cents": 600}] if menu is None else menu
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name=name,
            category="addon",
            tags=["drinks", "snacks", "family"],
        ),
        poi_detail={
            "poi_id": candidate_id,
            "vendor_id": candidate_id,
            "menu": resolved_menu,
        },
        opening_hours={"is_open": opening_is_open},
        tool_results=[
            _tool_result(
                "get_poi_detail",
                candidate_id,
                response_json={"poi": {"poi_id": candidate_id}},
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
    others: list[EnrichedCandidate] | None = None,
    routes: list[RouteMatrixEntry] | None = None,
    world_profile: str | None = None,
) -> CandidateEnrichmentResult:
    return CandidateEnrichmentResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        enriched_activity_candidates=[_activity()] if activities is None else activities,
        enriched_dining_candidates=[_dining()] if dining is None else dining,
        enriched_other_candidates=[] if others is None else others,
        route_matrix=[_route()] if routes is None else routes,
        world_profile=world_profile,
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
        "reserve_restaurant",
        "book_ticket",
    ]
    assert draft.proposed_actions[0].reason == "餐厅有可订座位，确认后可提前锁定晚餐座位。"
    assert draft.proposed_actions[1].reason == "票务可用，确认后可提前锁定入场名额。"
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
        "reserve_restaurant",
        "book_ticket",
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


def test_generator_appends_order_addon_for_explicit_addon_request_when_evidence_is_complete() -> None:
    addon_route_event_id = uuid4()
    result = DeterministicItineraryGenerator().generate(
        _plan(
            raw_text=(
                "This afternoon I want a nearby family plan with a light citywalk feel, "
                "and please add an easy drink stop if it fits."
            ),
        ),
        _enrichment(
            others=[_addon()],
            routes=[
                _route(),
                _route(
                    origin_candidate_id="restaurant_light_001",
                    destination_candidate_id="addon_drinks_001",
                    duration_minutes=13,
                    distance_meters=900,
                    tool_event_id=addon_route_event_id,
                ),
            ],
        ),
    )

    draft = result.drafts[0]
    assert [action.action_type for action in draft.proposed_actions] == [
        "reserve_restaurant",
        "book_ticket",
        "order_addon",
    ]
    addon_action = draft.proposed_actions[-1]
    assert addon_action.target_id == "addon_drinks_001"
    assert addon_action.payload == {
        "vendor_id": "addon_drinks_001",
        "items": [{"sku": "water", "quantity": 3}],
    }
    assert addon_action.reason == "补给点可顺路到达，确认后可提前下单补水或小食。"
    assert draft.evidence["selected_addon"]["candidate_id"] == "addon_drinks_001"
    assert draft.evidence["selected_addon"]["name"] == "小水分补给站"
    assert draft.evidence["selected_addon"]["route_tool_event_id"] == addon_route_event_id


def test_generator_adds_send_message_for_family_spouse_path_after_other_write_actions() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(
            raw_text=(
                "This afternoon I want to go out with my wife and child for a few hours. "
                "Not too far. My child is 5, and my wife is trying to eat lighter. "
                "Please add an easy drink stop if it fits."
            ),
        ),
        _enrichment(
            world_profile="family_afternoon",
            others=[_addon()],
            routes=[
                _route(),
                _route(
                    origin_candidate_id="restaurant_light_001",
                    destination_candidate_id="addon_drinks_001",
                    duration_minutes=13,
                    distance_meters=900,
                ),
            ],
        ),
    )

    draft = result.drafts[0]
    assert [action.action_type for action in draft.proposed_actions] == [
        "reserve_restaurant",
        "book_ticket",
        "order_addon",
        "send_message",
    ]
    send_message = draft.proposed_actions[-1]
    assert send_message.target_id == "wife"
    assert send_message.payload["recipient"] == "wife"
    assert isinstance(send_message.payload["message"], str)
    assert send_message.payload["message"]
    assert "\u5f90\u6c47\u4eb2\u5b50\u79d1\u5b66\u9986" in send_message.payload["message"]
    assert "\u7eff\u7897\u5bb6\u5ead\u8f7b\u98df" in send_message.payload["message"]
    assert send_message.reason == (
        "\u786e\u8ba4\u540e\u4f1a\u628a\u5b89\u6392\u6d88\u606f\u53d1\u7ed9"
        "\u540c\u884c\u5bb6\u4eba\uff0c\u65b9\u4fbf\u540c\u6b65\u884c\u7a0b\u3002"
    )
    assert draft.evidence["post_confirmation_message"] == {
        "recipient": "wife",
        "recipient_label": "\u59bb\u5b50",
        "message_preview": send_message.payload["message"],
        "trigger_rule": "family_spouse_confirmation_v0",
    }


def test_generator_skips_send_message_without_family_world_profile() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(
            raw_text=(
                "This afternoon I want to go out with my wife and child for a few hours. "
                "Please add an easy drink stop if it fits."
            ),
        ),
        _enrichment(
            world_profile="friends_gathering",
            others=[_addon()],
            routes=[
                _route(),
                _route(
                    origin_candidate_id="restaurant_light_001",
                    destination_candidate_id="addon_drinks_001",
                ),
            ],
        ),
    )

    assert [action.action_type for action in result.drafts[0].proposed_actions] == [
        "reserve_restaurant",
        "book_ticket",
        "order_addon",
    ]
    assert "post_confirmation_message" not in result.drafts[0].evidence


def test_generator_skips_send_message_without_spouse_keyword() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(
            raw_text=(
                "This afternoon I want to go out with my child for a few hours. "
                "Please add an easy drink stop if it fits."
            ),
        ),
        _enrichment(
            world_profile="family_afternoon",
            others=[_addon()],
            routes=[
                _route(),
                _route(
                    origin_candidate_id="restaurant_light_001",
                    destination_candidate_id="addon_drinks_001",
                ),
            ],
        ),
    )

    assert [action.action_type for action in result.drafts[0].proposed_actions] == [
        "reserve_restaurant",
        "book_ticket",
        "order_addon",
    ]
    assert "post_confirmation_message" not in result.drafts[0].evidence


def test_generator_skips_send_message_when_no_earlier_write_action_exists() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(
            raw_text="This afternoon I want to go out with my wife and child for a few hours.",
        ),
        _enrichment(
            world_profile="family_afternoon",
            activities=[_activity(ticket_available=None)],
            dining=[_dining(table_available=None, queue_status=None)],
        ),
    )

    assert result.drafts[0].proposed_actions == []
    assert "post_confirmation_message" not in result.drafts[0].evidence


def test_generator_skips_order_addon_when_menu_or_route_evidence_is_missing() -> None:
    missing_water = DeterministicItineraryGenerator().generate(
        _plan(raw_text="Please add a drink stop if it fits."),
        _enrichment(
            others=[_addon(menu=[{"sku": "fruit_cup", "name": "水果杯", "price_cents": 1800}])],
            routes=[
                _route(),
                _route(
                    origin_candidate_id="restaurant_light_001",
                    destination_candidate_id="addon_drinks_001",
                ),
            ],
        ),
    )
    missing_route = DeterministicItineraryGenerator().generate(
        _plan(raw_text="Please add a drink stop if it fits."),
        _enrichment(
            others=[_addon()],
            routes=[_route()],
        ),
    )

    assert [action.action_type for action in missing_water.drafts[0].proposed_actions] == [
        "reserve_restaurant",
        "book_ticket",
    ]
    assert [action.action_type for action in missing_route.drafts[0].proposed_actions] == [
        "reserve_restaurant",
        "book_ticket",
    ]


@pytest.mark.parametrize(
    ("plan_kwargs", "activity", "dining", "expected_summary", "expected_reasons", "expected_activity_note", "expected_dining_note"),
    [
        (
            {
                "raw_text": "friends nearby this afternoon",
                "scenario_type": "friends",
                "adults": 3,
                "children_ages": [],
                "child_friendly": False,
            },
            _activity("activity_lawn_301", name="苏河边草坪聚会点", tags=["group_friendly", "hangout"]),
            _dining(
                "restaurant_yard_301",
                name="庭院分享餐吧",
                tags=["casual_dining", "friends_group", "sharing_plates"],
            ),
            "和朋友散步聊天",
            ["已选择适合朋友聚会的活动", "已选择适合分享的用餐", "活动到餐厅路线已验证"],
            "根据候选详情、营业时间和聚会氛围安排朋友同行活动。",
            "结合分享型用餐、朋友聚会氛围和桌位信息安排晚餐。",
        ),
        (
            {
                "raw_text": "solo nearby this afternoon",
                "scenario_type": "solo",
                "adults": 1,
                "children_ages": [],
                "child_friendly": False,
            },
            _activity("activity_gallery_001", name="静安轻展馆", tags=["indoor", "museum", "light_activity"]),
            _dining("restaurant_light_001", name="静安清淡食堂", tags=["lighter_options", "quiet", "light_meal"]),
            "一个人轻松逛逛",
            ["已选择适合单人放松的活动", "已选择轻量简餐", "活动到餐厅路线已验证"],
            "根据候选详情、营业时间和轻松节奏安排单人活动。",
            "结合简餐偏好、安静程度和桌位信息安排用餐。",
        ),
        (
            {
                "raw_text": "和伴侣 citywalk 一下",
                "scenario_type": "unknown",
                "adults": 2,
                "children_ages": [],
                "child_friendly": False,
            },
            _activity("activity_citywalk_201", name="法式街区漫步", tags=["citywalk", "gallery"]),
            _dining("restaurant_light_201", name="小馆轻食", tags=["date_friendly", "light_meal"]),
            "和伴侣慢慢逛",
            ["已选择适合两人同行的活动", "已选择适合约会节奏的用餐", "活动到餐厅路线已验证"],
            "根据候选详情、营业时间和两人同行节奏安排活动。",
            "结合约会氛围、轻食偏好和桌位信息安排晚餐。",
        ),
        (
            {
                "raw_text": "下雨了，想找室内活动",
                "scenario_type": "friends",
                "adults": 2,
                "children_ages": [],
                "child_friendly": False,
            },
            _activity("activity_market_401", name="室内市集", tags=["indoor", "market"]),
            _dining("restaurant_soup_401", name="热汤简餐屋", tags=["comfort_food", "nearby", "warm_food"]),
            "室内避雨活动",
            ["已选择雨天可行的室内活动", "已选择适合雨天的热食简餐", "活动到餐厅路线已验证"],
            "根据候选详情、营业时间和室内可行性安排雨天活动。",
            "结合热食偏好、就近便利度和桌位信息安排雨天用餐。",
        ),
        (
            {
                "raw_text": "预算有限，找便宜点的",
                "scenario_type": "solo",
                "adults": 1,
                "children_ages": [],
                "child_friendly": False,
            },
            _activity("activity_park_501", name="河边免费公园步道", tags=["free_activity", "light_activity"]),
            _dining("restaurant_bento_501", name="平价便当小馆", tags=["budget_limited", "value_set", "quick_meal"]),
            "低预算活动",
            ["已选择免费或低价活动", "已选择预算友好的用餐", "活动到餐厅路线已验证"],
            "根据候选详情、营业时间和价格友好度安排低预算活动。",
            "结合预算限制、出餐效率和桌位信息安排平价用餐。",
        ),
    ],
)
def test_generator_uses_scenario_specific_copy(
    plan_kwargs,
    activity,
    dining,
    expected_summary,
    expected_reasons,
    expected_activity_note,
    expected_dining_note,
) -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(**plan_kwargs),
        _enrichment(activities=[activity], dining=[dining], routes=[_route(origin_candidate_id=activity.candidate.candidate_id, destination_candidate_id=dining.candidate.candidate_id)]),
    )

    draft = result.drafts[0]
    assert expected_summary in draft.summary
    assert draft.feasibility.reasons == expected_reasons
    assert draft.timeline[0].notes == [expected_activity_note]
    assert draft.timeline[2].notes == [expected_dining_note]
    assert "亲子活动" not in draft.summary


def test_generator_falls_back_to_generic_copy_for_ambiguous_non_family_cases() -> None:
    result = DeterministicItineraryGenerator().generate(
        _plan(
            raw_text="想在附近安排一下下午活动",
            scenario_type="unknown",
            adults=2,
            children_ages=[],
            child_friendly=False,
        ),
        _enrichment(
            activities=[_activity("activity_generic", name="附近活动点", tags=["quiet"])],
            dining=[_dining("restaurant_generic", name="附近餐厅", tags=["casual"])],
            routes=[_route(origin_candidate_id="activity_generic", destination_candidate_id="restaurant_generic")],
        ),
    )

    draft = result.drafts[0]
    assert draft.summary == "先去附近活动点安排活动，再去附近餐厅用餐，中间步行约12分钟。"
    assert draft.feasibility.reasons == ["已选择可行活动", "已选择可行用餐", "活动到餐厅路线已验证"]
    assert draft.timeline[0].notes == ["根据候选详情、营业时间和可用性安排活动。"]
    assert draft.timeline[2].notes == ["结合用餐偏好和桌位信息安排用餐。"]
