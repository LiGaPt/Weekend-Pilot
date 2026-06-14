from __future__ import annotations

from uuid import UUID, uuid4

from backend.app.planning import (
    Candidate,
    CandidateEnrichmentResult,
    DeterministicItineraryGenerator,
    EnrichedCandidate,
    EnrichmentToolResult,
    IntentConstraints,
    ItineraryDraft,
    ItineraryDraftResult,
    LocalLifeIntent,
    ParticipantProfile,
    QueryPlan,
    RouteMatrixEntry,
    TimeWindow,
)
from backend.app.review import FinalReviewGate


def _intent(
    *,
    child_friendly: bool = True,
    light_dining: bool = True,
    max_distance_km: int | None = 8,
    duration_hours_min: int | None = 4,
    duration_hours_max: int | None = 6,
) -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="family afternoon",
        scenario_type="family",
        participants=ParticipantProfile(adults=2, children_ages=[5]),
        time_window=TimeWindow(
            duration_hours_min=duration_hours_min,
            duration_hours_max=duration_hours_max,
        ),
        constraints=IntentConstraints(
            child_friendly=child_friendly,
            max_distance_km=max_distance_km,
        ),
        activity_preferences=["child_friendly"] if child_friendly else [],
        dining_preferences=["lighter_options"] if light_dining else [],
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
    category: str,
    tags: list[str] | None = None,
    tool_event_id: UUID | None = None,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        name=candidate_id,
        category=category,
        provider="mock_world",
        address=f"{candidate_id} address",
        tags=tags or [],
        raw_payload={"poi_id": candidate_id},
        source_call_index=0,
        tool_event_id=tool_event_id,
    )


def _tool_result(tool_name: str, candidate_id: str) -> EnrichmentToolResult:
    return EnrichmentToolResult(
        stage="candidate_enrichment",
        candidate_id=candidate_id,
        tool_name=tool_name,
        provider="mock_world",
        status="succeeded",
        response_json={},
        tool_event_id=uuid4(),
    )


def _activity(
    candidate_id: str = "activity_museum_001",
    *,
    tags: list[str] | None = None,
) -> EnrichedCandidate:
    candidate_tags = ["child_friendly", "indoor"] if tags is None else tags
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            category="activity",
            tags=candidate_tags,
        ),
        poi_detail={"poi_id": candidate_id, "tags": candidate_tags},
        opening_hours={"is_open": True},
        ticket_availability={
            "poi_id": candidate_id,
            "available": True,
            "time_slots": ["13:30"],
            "remaining": 12,
        },
        tool_results=[_tool_result("get_poi_detail", candidate_id)],
    )


def _dining(
    candidate_id: str = "restaurant_light_001",
    *,
    tags: list[str] | None = None,
    table_available: bool = True,
    queue_status: str = "open",
) -> EnrichedCandidate:
    candidate_tags = ["child_friendly", "lighter_options"] if tags is None else tags
    queue = {
        "queue_id": f"queue_{candidate_id}",
        "poi_id": candidate_id,
        "status": queue_status,
        "wait_minutes": 10,
    }
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            category="dining",
            tags=candidate_tags,
        ),
        poi_detail={
            "poi_id": candidate_id,
            "tags": candidate_tags,
        },
        opening_hours={"is_open": True},
        queue=queue,
        table_availability={
            "restaurant_id": candidate_id,
            "available": table_available,
            "time_slots": ["17:30"],
            "max_party_size": 4,
        },
        tool_results=[_tool_result("get_poi_detail", candidate_id)],
    )


def _addon(
    candidate_id: str = "addon_drinks_001",
    *,
    menu: list[dict] | None = None,
) -> EnrichedCandidate:
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            category="addon",
            tags=["drinks", "snacks"],
        ),
        poi_detail={
            "poi_id": candidate_id,
            "vendor_id": candidate_id,
            "menu": [{"sku": "water", "price_cents": 600}] if menu is None else menu,
        },
        opening_hours={"is_open": True},
        tool_results=[_tool_result("get_poi_detail", candidate_id)],
    )


def _route(
    origin_candidate_id: str = "activity_museum_001",
    destination_candidate_id: str = "restaurant_light_001",
    *,
    status: str = "succeeded",
    distance_meters: int | None = 850,
    duration_minutes: int | None = 12,
) -> RouteMatrixEntry:
    return RouteMatrixEntry(
        origin_candidate_id=origin_candidate_id,
        destination_candidate_id=destination_candidate_id,
        provider="mock_world",
        mode="walking",
        status=status,
        route_json={"summary": "Short walk"},
        distance_meters=distance_meters,
        duration_minutes=duration_minutes,
        tool_event_id=uuid4(),
    )


def _enrichment(
    *,
    run_id: UUID | None = None,
    activities: list[EnrichedCandidate] | None = None,
    dining: list[EnrichedCandidate] | None = None,
    others: list[EnrichedCandidate] | None = None,
    routes: list[RouteMatrixEntry] | None = None,
    provider_profile: str = "mock_world",
) -> CandidateEnrichmentResult:
    return CandidateEnrichmentResult(
        run_id=run_id or uuid4(),
        provider_profile=provider_profile,
        enriched_activity_candidates=[_activity()] if activities is None else activities,
        enriched_dining_candidates=[_dining()] if dining is None else dining,
        enriched_other_candidates=[] if others is None else others,
        route_matrix=[_route()] if routes is None else routes,
        enricher_version="test-enricher",
    )


def _drafts(plan: QueryPlan, enrichment: CandidateEnrichmentResult) -> ItineraryDraftResult:
    return DeterministicItineraryGenerator().generate(plan, enrichment)


def _draft_result(
    enrichment: CandidateEnrichmentResult,
    drafts: list[ItineraryDraft],
    *,
    provider_profile: str | None = None,
) -> ItineraryDraftResult:
    return ItineraryDraftResult(
        run_id=enrichment.run_id,
        provider_profile=provider_profile or enrichment.provider_profile,
        drafts=drafts,
        generator_version="test-generator",
    )


def _single_draft() -> tuple[QueryPlan, CandidateEnrichmentResult, ItineraryDraftResult, ItineraryDraft]:
    plan = _plan()
    enrichment = _enrichment()
    drafts = _drafts(plan, enrichment)
    return plan, enrichment, drafts, drafts.drafts[0]


def _check_names(checks) -> set[str]:
    return {check.check_name for check in checks}


def test_valid_draft_is_approved_with_all_required_checks() -> None:
    plan, enrichment, drafts, draft = _single_draft()
    assert any(item.item_type == "buffer" and item.duration_minutes == 0 for item in draft.timeline)

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "approved"
    assert result.safe_to_present is True
    assert result.errors == []
    assert result.warnings == []
    assert result.gate_version == "final_review_gate_v1"
    assert result.reviewed_drafts[0].decision == "approved"
    assert _check_names(result.checks) >= {
        "run_id_consistency",
        "pre_confirmation_no_actions",
        "draft_exists",
        "activity_present",
        "dining_present",
        "candidate_ids_verified",
        "route_present",
        "route_verified",
        "timeline_duration",
        "child_friendly_constraint",
        "dining_preference_constraint",
        "distance_constraint",
        "actions_require_confirmation",
        "actions_reference_draft_objects",
        "actions_have_no_execution_fields",
        "sensitive_payload_scan",
    }


def test_required_timeline_item_with_zero_duration_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    timeline = [
        item.model_copy(update={"duration_minutes": 0}) if item.item_type == "activity" else item
        for item in draft.timeline
    ]
    bad_draft = draft.model_copy(update={"timeline": timeline})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "timeline_duration" in _check_names(result.reviewed_drafts[0].errors)


def test_timeline_duration_outside_requested_range_warns_without_blocking() -> None:
    plan = _plan(duration_hours_min=5, duration_hours_max=6)
    enrichment = _enrichment()
    drafts = _drafts(plan, enrichment)

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "approved_with_warnings"
    assert result.safe_to_present is True
    assert _check_names(result.warnings) == {"timeline_duration"}


def test_empty_drafts_are_blocked_with_draft_exists_error() -> None:
    plan = _plan()
    enrichment = _enrichment()
    drafts = _draft_result(enrichment, [])

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "blocked"
    assert result.safe_to_present is False
    assert _check_names(result.errors) == {"draft_exists"}


def test_missing_activity_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_draft = draft.model_copy(update={"activity": None})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert result.reviewed_drafts[0].safe_to_present is False
    assert "activity_present" in _check_names(result.reviewed_drafts[0].errors)


def test_missing_dining_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_draft = draft.model_copy(update={"dining": None})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "dining_present" in _check_names(result.reviewed_drafts[0].errors)


def test_queue_closed_dining_blocks_the_draft() -> None:
    plan = _plan()
    enrichment = _enrichment(dining=[_dining(queue_status="closed")])
    drafts = _drafts(plan, enrichment)

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "blocked"
    blocked_check = next(
        check
        for check in result.reviewed_drafts[0].errors
        if check.check_name == "dining_availability"
    )
    assert blocked_check.details["availability_status"] == "queue_closed"


def test_table_unavailable_dining_blocks_the_draft_even_when_queue_is_open() -> None:
    plan = _plan()
    enrichment = _enrichment(dining=[_dining(table_available=False, queue_status="open")])
    drafts = _drafts(plan, enrichment)

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "blocked"
    blocked_check = next(
        check
        for check in result.reviewed_drafts[0].errors
        if check.check_name == "dining_availability"
    )
    assert blocked_check.details["availability_status"] == "table_unavailable"


def test_unverified_candidate_id_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    unknown_activity = draft.activity.model_copy(update={"candidate_id": "unknown_activity"})
    bad_draft = draft.model_copy(update={"activity": unknown_activity})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "candidate_ids_verified" in _check_names(result.reviewed_drafts[0].errors)


def test_missing_route_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_draft = draft.model_copy(update={"route": None})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "route_present" in _check_names(result.reviewed_drafts[0].errors)


def test_mismatched_route_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_route = draft.route.model_copy(update={"origin_candidate_id": "other_activity"})
    bad_draft = draft.model_copy(update={"route": bad_route})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "route_verified" in _check_names(result.reviewed_drafts[0].errors)


def test_route_missing_from_enrichment_evidence_blocks_the_draft() -> None:
    plan, enrichment, drafts, _ = _single_draft()
    enrichment_without_routes = enrichment.model_copy(update={"route_matrix": []})

    result = FinalReviewGate().review(plan, enrichment_without_routes, drafts)

    assert result.decision == "blocked"
    assert "route_verified" in _check_names(result.reviewed_drafts[0].errors)


def test_action_without_confirmation_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    actions = [draft.proposed_actions[0].model_copy(update={"requires_confirmation": False})]
    bad_draft = draft.model_copy(update={"proposed_actions": actions})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "actions_require_confirmation" in _check_names(result.reviewed_drafts[0].errors)


def test_action_with_execution_field_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    action = draft.proposed_actions[0]
    bad_action = action.model_copy(update={"payload": {**action.payload, "idempotency_key": "abc"}})
    bad_draft = draft.model_copy(update={"proposed_actions": [bad_action]})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "actions_have_no_execution_fields" in _check_names(result.reviewed_drafts[0].errors)


def test_action_targeting_unknown_object_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_action = draft.proposed_actions[0].model_copy(update={"target_id": "outside_target"})
    bad_draft = draft.model_copy(update={"proposed_actions": [bad_action]})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "actions_reference_draft_objects" in _check_names(result.reviewed_drafts[0].errors)


def test_unknown_action_type_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_action = draft.proposed_actions[0].model_copy(update={"action_type": "send_message"})
    bad_draft = draft.model_copy(update={"proposed_actions": [bad_action]})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "actions_reference_draft_objects" in _check_names(result.reviewed_drafts[0].errors)


def test_valid_backed_send_message_action_is_approved() -> None:
    plan, enrichment, _, draft = _single_draft()
    message_action = draft.proposed_actions[0].model_copy(
        update={
            "action_ref": "draft_1_action_3",
            "action_type": "send_message",
            "target_id": "wife",
            "payload": {
                "recipient": "wife",
                "message": "Plan confirmed.",
            },
            "reason": "Post-confirmation message.",
        }
    )
    message_draft = draft.model_copy(
        update={
            "proposed_actions": [*draft.proposed_actions, message_action],
            "evidence": {
                **draft.evidence,
                "post_confirmation_message": {
                    "recipient": "wife",
                    "recipient_label": "\u59bb\u5b50",
                    "message_preview": "Plan confirmed.",
                    "trigger_rule": "family_spouse_confirmation_v0",
                },
            },
        }
    )

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [message_draft]))

    assert result.decision == "approved"
    assert result.reviewed_drafts[0].decision == "approved"


def test_send_message_without_backing_evidence_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    message_action = draft.proposed_actions[0].model_copy(
        update={
            "action_ref": "draft_1_action_3",
            "action_type": "send_message",
            "target_id": "wife",
            "payload": {
                "recipient": "wife",
                "message": "Plan confirmed.",
            },
            "reason": "Post-confirmation message.",
        }
    )
    message_draft = draft.model_copy(update={"proposed_actions": [*draft.proposed_actions, message_action]})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [message_draft]))

    assert result.decision == "blocked"
    assert "actions_reference_draft_objects" in _check_names(result.reviewed_drafts[0].errors)


def test_send_message_with_mismatched_recipient_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    message_action = draft.proposed_actions[0].model_copy(
        update={
            "action_ref": "draft_1_action_3",
            "action_type": "send_message",
            "target_id": "self",
            "payload": {
                "recipient": "wife",
                "message": "Plan confirmed.",
            },
            "reason": "Post-confirmation message.",
        }
    )
    message_draft = draft.model_copy(
        update={
            "proposed_actions": [*draft.proposed_actions, message_action],
            "evidence": {
                **draft.evidence,
                "post_confirmation_message": {
                    "recipient": "wife",
                    "recipient_label": "\u59bb\u5b50",
                    "message_preview": "Plan confirmed.",
                    "trigger_rule": "family_spouse_confirmation_v0",
                },
            },
        }
    )

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [message_draft]))

    assert result.decision == "blocked"
    assert "actions_reference_draft_objects" in _check_names(result.reviewed_drafts[0].errors)


def test_send_message_with_empty_message_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    message_action = draft.proposed_actions[0].model_copy(
        update={
            "action_ref": "draft_1_action_3",
            "action_type": "send_message",
            "target_id": "wife",
            "payload": {
                "recipient": "wife",
                "message": "",
            },
            "reason": "Post-confirmation message.",
        }
    )
    message_draft = draft.model_copy(
        update={
            "proposed_actions": [*draft.proposed_actions, message_action],
            "evidence": {
                **draft.evidence,
                "post_confirmation_message": {
                    "recipient": "wife",
                    "recipient_label": "\u59bb\u5b50",
                    "message_preview": "Plan confirmed.",
                    "trigger_rule": "family_spouse_confirmation_v0",
                },
            },
        }
    )

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [message_draft]))

    assert result.decision == "blocked"
    assert "actions_reference_draft_objects" in _check_names(result.reviewed_drafts[0].errors)


def test_valid_backed_order_addon_action_is_approved() -> None:
    plan, _, _, draft = _single_draft()
    enrichment = _enrichment(
        others=[_addon()],
        routes=[
            _route(),
            _route(
                origin_candidate_id="restaurant_light_001",
                destination_candidate_id="addon_drinks_001",
            ),
        ],
    )
    addon_action = draft.proposed_actions[0].model_copy(
        update={
            "action_ref": "draft_1_action_3",
            "action_type": "order_addon",
            "target_id": "addon_drinks_001",
            "payload": {
                "vendor_id": "addon_drinks_001",
                "items": [{"sku": "water", "quantity": 3}],
            },
            "reason": "补给点可顺路到达，确认后可提前下单补水或小食。",
        }
    )
    addon_draft = draft.model_copy(
        update={
            "proposed_actions": [*draft.proposed_actions, addon_action],
            "evidence": {
                **draft.evidence,
                "selected_addon": {
                    "candidate_id": "addon_drinks_001",
                    "name": "小水分补给站",
                    "route_key": ["restaurant_light_001", "addon_drinks_001"],
                },
            },
        }
    )

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [addon_draft]))

    assert result.decision == "approved"
    assert result.reviewed_drafts[0].decision == "approved"


def test_order_addon_with_unbacked_payload_blocks_the_draft() -> None:
    plan, _, _, draft = _single_draft()
    enrichment = _enrichment(others=[_addon()])
    addon_action = draft.proposed_actions[0].model_copy(
        update={
            "action_ref": "draft_1_action_3",
            "action_type": "order_addon",
            "target_id": "addon_drinks_001",
            "payload": {
                "vendor_id": "addon_drinks_001",
                "items": [],
            },
            "reason": "补给点可顺路到达，确认后可提前下单补水或小食。",
        }
    )
    addon_draft = draft.model_copy(
        update={
            "proposed_actions": [*draft.proposed_actions, addon_action],
            "evidence": {
                **draft.evidence,
                "selected_addon": {
                    "candidate_id": "addon_drinks_001",
                    "name": "小水分补给站",
                    "route_key": ["restaurant_light_001", "addon_drinks_001"],
                },
            },
        }
    )

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [addon_draft]))

    assert result.decision == "blocked"
    assert "actions_reference_draft_objects" in _check_names(result.reviewed_drafts[0].errors)


def test_nonzero_pre_confirmation_action_count_blocks_globally() -> None:
    plan, enrichment, drafts, _ = _single_draft()

    result = FinalReviewGate().review(
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=1,
    )

    assert result.decision == "blocked"
    assert result.safe_to_present is False
    assert "pre_confirmation_no_actions" in _check_names(result.errors)


def test_sensitive_key_in_draft_payload_blocks_the_draft() -> None:
    plan, enrichment, _, draft = _single_draft()
    bad_draft = draft.model_copy(update={"evidence": {"debug_trace": {"node": "x"}}})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [bad_draft]))

    assert result.decision == "blocked"
    assert "sensitive_payload_scan" in _check_names(result.reviewed_drafts[0].errors)


def test_child_friendly_and_light_dining_evidence_gaps_warn() -> None:
    plan = _plan()
    enrichment = _enrichment(
        activities=[_activity(tags=[])],
        dining=[_dining(tags=[])],
    )
    drafts = _drafts(plan, enrichment)

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "approved_with_warnings"
    assert _check_names(result.warnings) >= {
        "child_friendly_constraint",
        "dining_preference_constraint",
    }


def test_distance_over_max_constraint_warns() -> None:
    plan = _plan(max_distance_km=8)
    enrichment = _enrichment(routes=[_route(distance_meters=9000)])
    drafts = _drafts(plan, enrichment)

    result = FinalReviewGate().review(plan, enrichment, drafts)

    assert result.decision == "approved_with_warnings"
    assert "distance_constraint" in _check_names(result.warnings)


def test_empty_proposed_actions_warn_without_blocking() -> None:
    plan, enrichment, _, draft = _single_draft()
    no_action_draft = draft.model_copy(update={"proposed_actions": []})

    result = FinalReviewGate().review(plan, enrichment, _draft_result(enrichment, [no_action_draft]))

    assert result.decision == "approved_with_warnings"
    assert result.reviewed_drafts[0].safe_to_present is True
    assert "actions_require_confirmation" in _check_names(result.reviewed_drafts[0].warnings)


def test_one_bad_draft_plus_one_good_draft_allows_top_level_with_warnings() -> None:
    plan, enrichment, _, good_draft = _single_draft()
    bad_draft = good_draft.model_copy(
        update={
            "draft_id": "bad_draft",
            "dining": None,
        }
    )

    result = FinalReviewGate().review(
        plan,
        enrichment,
        _draft_result(enrichment, [bad_draft, good_draft]),
    )

    assert result.decision == "approved_with_warnings"
    assert result.safe_to_present is True
    assert [review.safe_to_present for review in result.reviewed_drafts] == [False, True]


def test_run_id_or_provider_profile_mismatch_blocks_globally() -> None:
    plan, enrichment, drafts, _ = _single_draft()
    mismatched_drafts = drafts.model_copy(
        update={
            "run_id": uuid4(),
            "provider_profile": "amap",
        }
    )

    result = FinalReviewGate().review(plan, enrichment, mismatched_drafts)

    assert result.decision == "blocked"
    assert "run_id_consistency" in _check_names(result.errors)
