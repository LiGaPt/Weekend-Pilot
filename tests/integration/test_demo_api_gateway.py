from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.agents import AgentResult, DeterministicValidatorRecoveryAgent, RecoveryDecision
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal, get_db
from backend.app.models.runtime import ActionLedger, AgentRun, ConversationSession, ConversationTurn, ToolEvent, User
from backend.app.providers.amap.errors import AMapConfigurationError
from backend.app.review.schemas import FinalReviewResult, ReviewCheck
from backend.app.runtime import get_redis_client
from backend.app.main import create_app
from backend.app.tool_gateway import ToolRateLimit, build_default_registry


TEST_PREFIX = "demo-api-gateway"
USER_INPUT = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
)
FRIENDS_GROUP_INPUT = (
    "This afternoon I want to hang out with friends nearby for a few hours. "
    "Start with an outdoor walk and chatting, then find a casual dinner place that's good for sharing. "
    "Not too far."
)
EXPLICIT_MOCK_WORLD_PRESETS = [
    (
        "family_afternoon",
        "今天下午想和妻子、5 岁孩子在附近出门玩几个小时，先安排室内亲子活动，再吃一顿清淡晚餐，不要太远。",
    ),
    (
        "friends_gathering",
        "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
    ),
    (
        "solo_afternoon",
        "今天下午想一个人在附近轻松待几个小时，先安排轻量活动，再吃一顿清淡的简餐，不要太远。",
    ),
    (
        "couple_afternoon",
        "今天下午想和伴侣在附近出门几个小时，先安排 citywalk，再吃一顿清淡晚餐，不要太远。",
    ),
    (
        "rainy_day_fallback",
        "今天下午想和朋友在附近待几个小时，外面下雨，优先安排室内活动，再找一家热一点的简餐，不要太远。",
    ),
    (
        "budget_lite",
        "今天下午想一个人在附近待几个小时，尽量控制预算，先安排免费或低价活动，再吃一顿便宜简餐，不要太远。",
    ),
]
EXPLICIT_PROFILE_COPY_EXPECTATIONS = {
    "friends_gathering": {
        "summary_fragment": "和朋友散步聊天",
        "reasons": ["已选择适合朋友聚会的活动", "已选择适合分享的用餐", "活动到餐厅路线已验证"],
        "activity_note": "根据候选详情、营业时间和聚会氛围安排朋友同行活动。",
        "dining_note": "结合分享型用餐、朋友聚会氛围和桌位信息安排晚餐。",
    },
    "solo_afternoon": {
        "summary_fragment": "一个人轻松逛逛",
        "reasons": ["已选择适合单人放松的活动", "已选择轻量简餐", "活动到餐厅路线已验证"],
        "activity_note": "根据候选详情、营业时间和轻松节奏安排单人活动。",
        "dining_note": "结合简餐偏好、安静程度和桌位信息安排用餐。",
    },
    "couple_afternoon": {
        "summary_fragment": "和伴侣慢慢逛",
        "reasons": ["已选择适合两人同行的活动", "已选择适合约会节奏的用餐", "活动到餐厅路线已验证"],
        "activity_note": "根据候选详情、营业时间和两人同行节奏安排活动。",
        "dining_note": "结合约会氛围、轻食偏好和桌位信息安排晚餐。",
    },
    "rainy_day_fallback": {
        "summary_fragment": "室内避雨活动",
        "reasons": ["已选择雨天可行的室内活动", "已选择适合雨天的热食简餐", "活动到餐厅路线已验证"],
        "activity_note": "根据候选详情、营业时间和室内可行性安排雨天活动。",
        "dining_note": "结合热食偏好、就近便利度和桌位信息安排雨天用餐。",
    },
    "budget_lite": {
        "summary_fragment": "低预算活动",
        "reasons": ["已选择免费或低价活动", "已选择预算友好的用餐", "活动到餐厅路线已验证"],
        "activity_note": "根据候选详情、营业时间和价格友好度安排低预算活动。",
        "dining_note": "结合预算限制、出餐效率和桌位信息安排平价用餐。",
    },
}
FORBIDDEN_RESPONSE_KEYS = {
    "action_id",
    "tool_event_id",
    "event_id",
    "idempotency_key",
    "api_key",
    "token",
    "secret",
    "authorization",
    "prompt",
    "debug_trace",
}
REDACTED_PUBLIC_RUN_FIELDS = {
    "trace_id",
    "tool_event_count",
    "node_history",
    "observability_status",
    "agent_roles",
}
PROGRESS_LABELS = {
    "understanding_request": "\u6b63\u5728\u7406\u89e3\u9700\u6c42",
    "planning_queries": "\u6b63\u5728\u89c4\u5212\u67e5\u8be2",
    "searching_activities": "\u6b63\u5728\u67e5\u8be2\u6e38\u73a9\u5730\u70b9",
    "searching_dining": "\u6b63\u5728\u67e5\u8be2\u9910\u5385",
    "checking_availability": "\u6b63\u5728\u68c0\u67e5\u8425\u4e1a\u4e0e\u53ef\u7528\u6027",
    "building_itinerary": "\u6b63\u5728\u7ec4\u5408\u884c\u7a0b",
    "checking_route_time": "\u6b63\u5728\u8ba1\u7b97\u8def\u7ebf\u4e0e\u65f6\u95f4",
    "reviewing_plan": "\u6b63\u5728\u590d\u6838\u65b9\u6848",
    "ready_for_confirmation": "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
    "executing_confirmed_actions": "\u5df2\u786e\u8ba4\uff0c\u6b63\u5728\u6267\u884c\u52a8\u4f5c",
}
READY_PROGRESS_HISTORY = [
    "understanding_request",
    "planning_queries",
    "searching_activities",
    "searching_dining",
    "checking_availability",
    "building_itinerary",
    "checking_route_time",
    "reviewing_plan",
    "ready_for_confirmation",
]
VAGUE_USER_INPUT = "想周末出去玩一下。"


class _FakeAmapPreviewProvider:
    name = "amap"

    def invoke(self, tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        if tool_name == "search_poi":
            if payload.get("canonical_category") == "activity":
                return {
                    "results": [
                        {
                            "id": "amap-activity-1",
                            "name": "Riverside Family Park",
                            "category": "Park",
                            "address": "1 Riverside Road",
                            "location": "121.480,31.230",
                            "source": "amap",
                        }
                    ]
                }
            return {
                "results": [
                    {
                        "id": "amap-dining-1",
                        "name": "Light Kitchen",
                        "category": "Restaurant",
                        "address": "8 Dining Road",
                        "location": "121.486,31.232",
                        "source": "amap",
                    }
                ]
            }
        if tool_name == "get_poi_detail":
            poi_id = str(payload.get("poi_id") or "")
            return {
                "poi": {
                    "poi_id": poi_id,
                    "description": f"Preview detail for {poi_id}.",
                }
            }
        if tool_name == "check_weather":
            return {"weather": {"city": "Shanghai", "condition": "Sunny"}}
        if tool_name == "check_route":
            return {
                "route": {
                    "mode": "walking",
                    "distance_meters": 1200,
                    "duration_minutes": 15,
                    "summary": "Walkable route between the preview POIs.",
                }
            }
        raise AssertionError(f"Unexpected tool {tool_name!r} for fake AMAP preview provider.")


def _build_fake_amap_registry():
    registry = build_default_registry(default_provider="amap")
    registry.register_provider(_FakeAmapPreviewProvider())
    return registry


@pytest.fixture()
def redis_client() -> Redis:
    client = get_redis_client()
    client.ping()
    return client


@pytest.fixture()
def trace_path() -> Path:
    directory = Path("var/test-traces") / str(uuid4())
    path = directory / "weekendpilot-traces.jsonl"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()
        if directory.exists():
            directory.rmdir()


@pytest.fixture()
def client(redis_client: Redis, trace_path: Path):
    app = create_app()
    case_ids: list[str] = []
    external_user_ids: list[str] = []
    settings = Settings(
        app_env=f"test-demo-api-{uuid4()}",
        local_trace_buffer_path=str(trace_path),
        langsmith_tracing=False,
    )

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client, case_ids, external_user_ids

    app.dependency_overrides.clear()
    cleanup = SessionLocal()
    try:
        if case_ids:
            cleanup.execute(delete(AgentRun).where(AgentRun.case_id.in_(case_ids)))
        if external_user_ids:
            cleanup.execute(delete(User).where(User.external_id.in_(external_user_ids)))
        cleanup.commit()
    finally:
        cleanup.close()


def _start_payload(
    case_ids: list[str],
    external_user_ids: list[str],
    *,
    user_input: str = USER_INPUT,
) -> dict[str, str]:
    suffix = str(uuid4())
    case_id = f"{TEST_PREFIX}-{suffix}"
    external_user_id = f"{TEST_PREFIX}-user-{suffix}"
    case_ids.append(case_id)
    external_user_ids.append(external_user_id)
    return {
        "user_input": user_input,
        "external_user_id": external_user_id,
        "display_name": "Web Demo Gateway Tester",
        "case_id": case_id,
    }


def _count_actions(session: Session, run_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id)
        )
        or 0
    )


def _count_write_tool_events(session: Session, run_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(ToolEvent).where(
                ToolEvent.run_id == run_id,
                ToolEvent.tool_type == "write",
            )
        )
        or 0
    )


def _demo_trace_id(session: Session, run_id: UUID) -> str | None:
    run = session.get(AgentRun, run_id)
    if run is None or not isinstance(run.metadata_json, dict):
        return None
    demo = run.metadata_json.get("demo")
    if not isinstance(demo, dict):
        return None
    trace_id = demo.get("trace_id")
    return trace_id if isinstance(trace_id, str) else None


def _load_run(session: Session, run_id: UUID) -> AgentRun:
    run = session.get(AgentRun, run_id)
    assert run is not None
    return run


def _assert_no_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        forbidden = FORBIDDEN_RESPONSE_KEYS.intersection(value)
        if forbidden == {"prompt"} and set(value).issubset({"prompt", "missing_fields"}):
            forbidden = set()
        assert forbidden == set()
        for child in value.values():
            _assert_no_forbidden_keys(child)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def _assert_public_run_redaction(payload: dict[str, object]) -> None:
    for key in REDACTED_PUBLIC_RUN_FIELDS:
        assert key not in payload


def _assert_plan_version(
    payload: dict[str, object],
    *,
    version_number: int,
    source_run_id: str | None,
    source_selected_plan_id: str | None,
) -> None:
    assert payload["plan_version"] == {
        "version_number": version_number,
        "version_label": f"v{version_number}",
        "source_run_id": source_run_id,
        "source_selected_plan_id": source_selected_plan_id,
    }


def _assert_progress(
    payload: dict[str, object],
    *,
    current_stage: str,
    stage_history: list[str],
) -> None:
    progress = payload["progress"]
    assert progress["schema_version"] == "public_demo_progress_v1"
    assert progress["current_stage"] == current_stage
    assert progress["current_label"] == PROGRESS_LABELS[current_stage]
    assert progress["stage_history"] == stage_history
    steps = progress["steps"]
    assert isinstance(steps, list)
    assert [step["stage"] for step in steps] == stage_history
    assert steps[-1]["status"] == "current"
    for index, stage in enumerate(stage_history):
        step = steps[index]
        assert step["label"] == PROGRESS_LABELS[stage]
        assert step["status"] == ("current" if index == len(stage_history) - 1 else "completed")
        assert isinstance(step["summary"], str)
        assert step["summary"]


def _progress_step_summary(payload: dict[str, object], stage: str) -> str:
    steps = payload["progress"]["steps"]
    for step in steps:
        if step["stage"] == stage:
            return step["summary"]
    raise AssertionError(f"Missing progress step {stage!r}")


def _assert_action_manifest_preview(plan: dict[str, object]) -> None:
    manifest = plan["action_manifest"]
    assert isinstance(manifest, dict)
    assert manifest["source"] == "proposed_actions"
    assert manifest["action_count"] == len(plan["proposed_actions"])
    assert len(manifest["actions"]) == manifest["action_count"]
    for index, action in enumerate(manifest["actions"], start=1):
        assert action["execution_order"] == index
        assert "idempotency_key" not in action
        assert "user_confirmed" not in action
        _assert_no_forbidden_keys(action["payload_preview"])


def _assert_action_manifest_confirmed(plan: dict[str, object]) -> None:
    manifest = plan["action_manifest"]
    assert isinstance(manifest, dict)
    assert manifest["source"] == "confirmed_actions"
    assert manifest["action_count"] == len(manifest["actions"])
    assert [action["execution_order"] for action in manifest["actions"]] == list(
        range(1, manifest["action_count"] + 1)
    )
    for action in manifest["actions"]:
        assert "idempotency_key" not in action
        assert "user_confirmed" not in action
        _assert_no_forbidden_keys(action["payload_preview"])


def _assert_turn_snapshot(
    turn: ConversationTurn,
    *,
    run_id: UUID,
    run_status: str,
    plan_version_label: str,
    clarification_missing_fields: list[str],
    selected_plan_id: str | None = None,
    plan_count: int | None = None,
) -> None:
    assert turn.run_id == run_id
    assert turn.trace_id is None or isinstance(turn.trace_id, str)
    assert turn.state_snapshot_json["schema_version"] == "conversation_turn_state_snapshot_v0"
    assert turn.state_snapshot_json["run_status"] == run_status
    assert turn.state_snapshot_json["selected_plan_id"] == selected_plan_id
    assert turn.state_snapshot_json["plan_version_label"] == plan_version_label
    assert turn.state_snapshot_json["clarification_missing_fields"] == clarification_missing_fields
    if plan_count is not None:
        assert turn.state_snapshot_json["plan_count"] == plan_count
    assert "session_id" not in turn.state_snapshot_json
    assert "trace_id" not in turn.state_snapshot_json
    assert "node_history" not in turn.state_snapshot_json
    assert "prompt" not in turn.state_snapshot_json
    progress = turn.state_snapshot_json["progress"]
    assert progress["schema_version"] == "public_demo_progress_v1"
    assert isinstance(progress["stage_history"], list)


def _read_sse_events(response) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    current_event: str | None = None
    current_data: list[str] = []
    for raw_line in response.iter_lines():
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line == "":
            if current_event is not None:
                events.append((current_event, json.loads("".join(current_data))))
            current_event = None
            current_data = []
            continue
        if line.startswith("event: "):
            current_event = line[len("event: ") :]
            continue
        if line.startswith("data: "):
            current_data.append(line[len("data: ") :])
    return events


def test_demo_run_stream_happy_path_emits_progress_then_final_summary(client) -> None:
    test_client, case_ids, external_user_ids = client

    with test_client.stream("POST", "/demo/runs/stream", json=_start_payload(case_ids, external_user_ids)) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _read_sse_events(response)

    progress_events = [payload for event_name, payload in events if event_name == "progress"]
    assert progress_events
    assert progress_events[0]["progress"]["current_stage"] == "understanding_request"
    for previous, current in zip(progress_events, progress_events[1:]):
        assert previous["progress"] != current["progress"]

    assert events[-1][0] == "summary"
    assert [event_name for event_name, _ in events].count("summary") == 1
    summary = events[-1][1]["summary"]
    _assert_no_forbidden_keys(summary)
    _assert_public_run_redaction(summary)
    assert summary["status"] == "awaiting_confirmation"
    _assert_progress(
        summary,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )

    run_id = summary["run_id"]
    status_response = test_client.get(f"/demo/runs/{run_id}")

    assert status_response.status_code == 200
    assert status_response.json() == summary


def test_demo_run_stream_happy_path_emits_ordered_search_milestones(client) -> None:
    test_client, case_ids, external_user_ids = client

    with test_client.stream("POST", "/demo/runs/stream", json=_start_payload(case_ids, external_user_ids)) as response:
        assert response.status_code == 200
        events = _read_sse_events(response)

    progress_events = [payload for event_name, payload in events if event_name == "progress"]
    assert progress_events

    activity_index = next(
        (
            index
            for index, payload in enumerate(progress_events)
            if payload["progress"]["current_stage"] == "searching_activities"
        ),
        None,
    )
    assert activity_index is not None
    assert _progress_step_summary(progress_events[activity_index], "searching_activities") == "已找到 5 个活动"

    dining_index = next(
        (
            index
            for index, payload in enumerate(progress_events)
            if payload["progress"]["current_stage"] == "searching_dining"
        ),
        None,
    )
    assert dining_index is not None
    assert _progress_step_summary(progress_events[dining_index], "searching_dining") == "已找到 5 个餐厅"

    assert activity_index < dining_index

    checking_index = next(
        (
            index
            for index, payload in enumerate(progress_events)
            if payload["progress"]["current_stage"] == "checking_availability"
        ),
        None,
    )
    if checking_index is not None:
        assert dining_index < checking_index


def test_demo_run_stream_clarification_path_ends_with_summary(client) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids, user_input=VAGUE_USER_INPUT)

    with test_client.stream("POST", "/demo/runs/stream", json=payload) as response:
        assert response.status_code == 200
        events = _read_sse_events(response)

    assert any(event_name == "progress" for event_name, _ in events)
    assert events[-1][0] == "summary"
    summary = events[-1][1]["summary"]
    _assert_no_forbidden_keys(summary)
    assert summary["status"] == "awaiting_clarification"
    assert summary["clarification"] is not None
    assert summary["plan_version"]["version_label"] == "v1"
    _assert_progress(
        summary,
        current_stage="planning_queries",
        stage_history=["understanding_request", "planning_queries"],
    )


def test_demo_run_stream_amap_configuration_error_emits_error_event(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids)
    payload["read_profile"] = "amap"

    def _raise_missing_config():
        raise AMapConfigurationError("AMAP API key is not configured.")

    monkeypatch.setattr("backend.app.workflow.nodes.build_amap_registry", _raise_missing_config)

    with test_client.stream("POST", "/demo/runs/stream", json=payload) as response:
        assert response.status_code == 200
        events = _read_sse_events(response)

    assert events == [
        (
            "error",
            {
                "event_index": 1,
                "run_id": None,
                "message": "AMAP read path is not configured for this environment.",
            },
        )
    ]


def test_demo_run_start_status_confirm_and_idempotent_replay(client) -> None:
    test_client, case_ids, external_user_ids = client

    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_confirmation"
    assert start_body["action_count"] == 0
    assert start_body["plans"]
    assert start_body["selected_plan_id"]
    _assert_plan_version(
        start_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        start_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    selected_start_plan = next(plan for plan in start_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(selected_start_plan)
    assert start_body["plans"][0]["confirmation"] is None
    run_id = UUID(start_body["run_id"])

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
        run = _load_run(db, run_id)
        assert run.session_id is not None
        conversation_session = db.get(ConversationSession, run.session_id)
        assert conversation_session is not None
        assert conversation_session.user_id == run.user_id
        assert conversation_session.channel == "web_demo"
        assert conversation_session.status == "active"
        assert conversation_session.metadata_json == {
            "source": "demo_api_v1",
            "case_id": case_ids[0],
            "selected_plan_index": 0,
        }
        turns = list(
            db.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == run.session_id)
                .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
            ).all()
        )
        assert len(turns) == 2
        assert turns[0].turn_index == 1
        assert turns[0].speaker_role == "user"
        assert turns[0].turn_type == "user_request"
        assert turns[0].content_text == USER_INPUT
        assert turns[0].payload_json == {}
        assert turns[1].turn_index == 2
        assert turns[1].speaker_role == "assistant"
        assert turns[1].turn_type == "assistant_plan_options"
        assert isinstance(turns[1].content_text, str)
        assert turns[1].content_text
        assert turns[1].payload_json == {
            "selected_plan_id": start_body["selected_plan_id"],
            "plan_ids": [plan["plan_id"] for plan in start_body["plans"]],
            "plan_count": len(start_body["plans"]),
            "run_status": "awaiting_confirmation",
        }
        assert "draft" not in turns[1].payload_json
        assert "plan_json" not in turns[1].payload_json
    finally:
        db.close()

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    _assert_no_forbidden_keys(confirm_body)
    _assert_public_run_redaction(confirm_body)
    assert confirm_body["run_id"] == str(run_id)
    assert confirm_body["status"] == "completed"
    assert confirm_body["action_count"] > 0
    _assert_progress(
        confirm_body,
        current_stage="executing_confirmed_actions",
        stage_history=[*READY_PROGRESS_HISTORY, "executing_confirmed_actions"],
    )
    selected_confirmed_plan = next(plan for plan in confirm_body["plans"] if plan["selected"])
    _assert_action_manifest_confirmed(selected_confirmed_plan)
    feedback = selected_confirmed_plan["feedback"]
    assert feedback["final_arrangement_message"]
    assert "搞定了" in feedback["final_arrangement_message"]
    assert "出发" in feedback["final_arrangement_message"]

    readback_response = test_client.get(f"/demo/runs/{run_id}")
    assert readback_response.status_code == 200
    readback_body = readback_response.json()
    _assert_no_forbidden_keys(readback_body)
    _assert_public_run_redaction(readback_body)
    assert readback_body["status"] == "completed"
    readback_selected_plan = next(plan for plan in readback_body["plans"] if plan["selected"])
    assert readback_selected_plan["feedback"]["final_arrangement_message"] == feedback["final_arrangement_message"]


def test_demo_rate_limits_are_scoped_by_external_user(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, case_ids, external_user_ids = client

    def _low_search_poi_limit(tool_name: str) -> ToolRateLimit | None:
        if tool_name == "search_poi":
            return ToolRateLimit(limit=2, window_seconds=60)
        return None

    monkeypatch.setattr("backend.app.tool_gateway.registry._read_rate_limit", _low_search_poi_limit)

    first_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))
    second_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_body = first_response.json()
    second_body = second_response.json()
    assert first_body["status"] == "awaiting_confirmation"
    assert second_body["status"] == "awaiting_confirmation"

    run_ids = [UUID(first_body["run_id"]), UUID(second_body["run_id"])]
    db = SessionLocal()
    try:
        events = list(
            db.scalars(select(ToolEvent).where(ToolEvent.run_id.in_(run_ids))).all()
        )
        search_poi_events = [event for event in events if event.tool_name == "search_poi"]
        assert search_poi_events
        assert all(event.status != "rate_limited" for event in search_poi_events)
    finally:
        db.close()


def test_demo_run_friends_group_start_persists_friends_world_and_confirms_successfully(client) -> None:
    test_client, case_ids, external_user_ids = client

    start_response = test_client.post(
        "/demo/runs",
        json=_start_payload(case_ids, external_user_ids, user_input=FRIENDS_GROUP_INPUT),
    )

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_confirmation"
    assert start_body["read_profile"] == "mock_world"
    assert start_body["action_count"] == 0
    assert start_body["plans"]
    assert start_body["selected_plan_id"]
    _assert_plan_version(
        start_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        start_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    selected_start_plan = next(plan for plan in start_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(selected_start_plan)
    expected_copy = EXPLICIT_PROFILE_COPY_EXPECTATIONS.get("friends_gathering")
    if expected_copy is not None:
        assert expected_copy["summary_fragment"] in selected_start_plan["summary"]
        assert "亲子活动" not in selected_start_plan["summary"]
        assert selected_start_plan["feasibility"]["reasons"] == expected_copy["reasons"]
        assert selected_start_plan["timeline"][0]["notes"] == [expected_copy["activity_note"]]
        assert selected_start_plan["timeline"][2]["notes"] == [expected_copy["dining_note"]]
    run_id = UUID(start_body["run_id"])

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
        run = _load_run(db, run_id)
        assert run.tool_profile == "mock_world"
        assert run.world_profile == "friends_gathering"
    finally:
        db.close()

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    _assert_no_forbidden_keys(confirm_body)
    _assert_public_run_redaction(confirm_body)
    assert confirm_body["run_id"] == str(run_id)
    assert confirm_body["status"] == "completed"
    assert confirm_body["action_count"] > 0
    _assert_progress(
        confirm_body,
        current_stage="executing_confirmed_actions",
        stage_history=[*READY_PROGRESS_HISTORY, "executing_confirmed_actions"],
    )
    assert _progress_step_summary(confirm_body, "executing_confirmed_actions") == (
        f"\u5df2\u5f00\u59cb\u6267\u884c {confirm_body['action_count']} \u4e2a\u786e\u8ba4\u52a8\u4f5c"
    )
    selected_confirmed_plan = next(plan for plan in confirm_body["plans"] if plan["selected"])
    _assert_action_manifest_confirmed(selected_confirmed_plan)
    assert selected_confirmed_plan["feedback"]["final_arrangement_message"]
    assert "搞定了" in selected_confirmed_plan["feedback"]["final_arrangement_message"]

    db = SessionLocal()
    try:
        run = _load_run(db, run_id)
        assert run.tool_profile == "mock_world"
        assert run.world_profile == "friends_gathering"
        assert _count_actions(db, run_id) > 0
    finally:
        db.close()


@pytest.mark.parametrize(("mock_world_profile", "user_input"), EXPLICIT_MOCK_WORLD_PRESETS)
def test_demo_run_start_with_explicit_mock_world_profile_persists_selected_world(
    client,
    mock_world_profile: str,
    user_input: str,
) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids, user_input=user_input)
    payload["mock_world_profile"] = mock_world_profile

    start_response = test_client.post("/demo/runs", json=payload)

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_confirmation"
    assert start_body["read_profile"] == "mock_world"
    assert start_body["action_count"] == 0
    assert start_body["selected_plan_id"]
    assert start_body["plans"]
    assert "mock_world_profile" not in start_body
    _assert_plan_version(
        start_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        start_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    selected_start_plan = next(plan for plan in start_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(selected_start_plan)
    run_id = UUID(start_body["run_id"])

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
        run = _load_run(db, run_id)
        assert run.tool_profile == "mock_world"
        assert run.world_profile == mock_world_profile
    finally:
        db.close()


def test_demo_run_addon_preview_and_confirmed_manifest_include_order_addon(client) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(
        case_ids,
        external_user_ids,
        user_input=(
            "This afternoon I want a light citywalk-style plan with my partner and 5-year-old, "
            "not too far from home, and include an easy drink or snack stop if it fits."
        ),
    )
    payload["mock_world_profile"] = "family_afternoon"

    start_response = test_client.post("/demo/runs", json=payload)

    assert start_response.status_code == 200
    start_body = start_response.json()
    assert start_body["status"] == "awaiting_confirmation"
    selected_start_plan = next(plan for plan in start_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(selected_start_plan)
    preview_addon_actions = [
        action for action in selected_start_plan["action_manifest"]["actions"] if action["action_type"] == "order_addon"
    ]
    assert len(preview_addon_actions) == 1
    assert preview_addon_actions[0]["target_id"] == "addon_drinks_001"
    run_id = UUID(start_body["run_id"])

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    assert confirm_body["status"] == "completed"
    selected_confirmed_plan = next(plan for plan in confirm_body["plans"] if plan["selected"])
    _assert_action_manifest_confirmed(selected_confirmed_plan)
    confirmed_addon_actions = [
        action
        for action in selected_confirmed_plan["action_manifest"]["actions"]
        if action["action_type"] == "order_addon"
    ]
    assert len(confirmed_addon_actions) == 1
    assert confirmed_addon_actions[0]["target_id"] == "addon_drinks_001"
    assert any(
        item.get("target_label") == "小水分补给站"
        for item in selected_confirmed_plan["feedback"]["completed_actions"]
    )


def test_demo_run_start_with_amap_reports_safe_configuration_error(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids)
    payload["read_profile"] = "amap"

    def _raise_missing_config():
        raise AMapConfigurationError("AMAP API key is not configured.")

    monkeypatch.setattr("backend.app.workflow.nodes.build_amap_registry", _raise_missing_config)

    response = test_client.post("/demo/runs", json=payload)

    assert response.status_code == 500
    assert response.json() == {
        "detail": "AMAP read path is not configured for this environment."
    }


def test_demo_run_amap_preview_stays_read_only_and_preserves_profile(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.workflow.nodes.build_amap_registry", _build_fake_amap_registry)
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids)
    payload["read_profile"] = "amap"

    start_response = test_client.post("/demo/runs", json=payload)

    assert start_response.status_code == 200
    start_body = start_response.json()
    assert start_body["status"] == "awaiting_confirmation"
    assert start_body["read_profile"] == "amap"
    assert start_body["action_count"] == 0
    _assert_progress(
        start_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    run_id = UUID(start_body["run_id"])

    db = SessionLocal()
    try:
        run = _load_run(db, run_id)
        assert run.tool_profile == "amap"
        assert run.world_profile == "amap_shanghai_live"
        assert _count_actions(db, run_id) == 0
        assert _count_write_tool_events(db, run_id) == 0
    finally:
        db.close()

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 409
    assert confirm_response.json() == {
        "detail": "AMAP read-only demo runs cannot be confirmed."
    }

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
        assert _count_write_tool_events(db, run_id) == 0
    finally:
        db.close()

    replan_response = test_client.post(
        f"/demo/runs/{run_id}/replan",
        json={
            "user_input": "Keep it nearby, but make the plan even lighter.",
            "selected_plan_index": 0,
        },
    )

    assert replan_response.status_code == 200
    replan_body = replan_response.json()
    assert replan_body["read_profile"] == "amap"
    assert replan_body["status"] == "awaiting_confirmation"
    assert replan_body["run_id"] != start_body["run_id"]
    _assert_progress(
        replan_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )

    db = SessionLocal()
    try:
        replan_run = _load_run(db, UUID(replan_body["run_id"]))
        assert replan_run.tool_profile == "amap"
        assert replan_run.world_profile == "amap_shanghai_live"
        assert _count_actions(db, replan_run.run_id) == 0
        assert _count_write_tool_events(db, replan_run.run_id) == 0
    finally:
        db.close()

    status_response = test_client.get(f"/demo/runs/{run_id}")

    assert status_response.status_code == 200
    status_body = status_response.json()
    _assert_public_run_redaction(status_body)
    assert status_body["run_id"] == str(run_id)
    assert status_body["selected_plan_id"] == start_body["selected_plan_id"]
    assert status_body["action_count"] == 0
    _assert_plan_version(
        status_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        status_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    status_selected_plan = next(plan for plan in status_body["plans"] if plan["selected"])
    manifest = status_selected_plan["action_manifest"]
    assert manifest == {
        "source": "none",
        "action_count": 0,
        "actions": [],
    }
    assert status_selected_plan["proposed_actions"] == []

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
        assert _count_write_tool_events(db, run_id) == 0
        assert _demo_trace_id(db, run_id) is not None
    finally:
        db.close()


def test_demo_run_decline_creates_no_actions_and_blocks_later_confirm(client) -> None:
    test_client, case_ids, external_user_ids = client
    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))
    assert start_response.status_code == 200
    run_id = start_response.json()["run_id"]

    decline_response = test_client.post(
        f"/demo/runs/{run_id}/decline",
        json={"declined_by": "web-demo-user", "reason": "用户选择暂不继续。"},
    )

    assert decline_response.status_code == 200
    decline_body = decline_response.json()
    assert decline_body["status"] == "declined"
    assert decline_body["action_count"] == 0
    _assert_progress(
        decline_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    assert _progress_step_summary(decline_body, "ready_for_confirmation") == (
        "\u5df2\u8bb0\u5f55\u672c\u6b21\u6682\u4e0d\u786e\u8ba4"
    )
    selected = next(plan for plan in decline_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(selected)
    assert selected["confirmation"]["status"] == "declined"

    db = SessionLocal()
    try:
        assert _count_actions(db, UUID(run_id)) == 0
    finally:
        db.close()

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 409


def test_demo_run_unknown_run_returns_404(client) -> None:
    test_client, _, _ = client

    response = test_client.get(f"/demo/runs/{uuid4()}")

    assert response.status_code == 404


def test_demo_run_status_route_keeps_public_shape_after_internal_route_addition(client) -> None:
    test_client, case_ids, external_user_ids = client
    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    run_id = start_response.json()["run_id"]

    status_response = test_client.get(f"/demo/runs/{run_id}")

    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["run_id"] == run_id
    assert "plans" in payload
    _assert_plan_version(
        payload,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        payload,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    assert _progress_step_summary(payload, "searching_activities") == "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8"
    assert _progress_step_summary(payload, "searching_dining") == "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385"
    assert "trace_id" not in payload
    assert "tool_event_count" not in payload
    assert "node_history" not in payload
    assert "observability_status" not in payload
    assert "agent_roles" not in payload
    assert "workflow_timing_summary" not in payload
    _assert_no_forbidden_keys(payload)


def test_demo_run_clarification_flow_reuses_session_and_keeps_version_v1(client) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids)
    payload["user_input"] = VAGUE_USER_INPUT

    start_response = test_client.post("/demo/runs", json=payload)

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_clarification"
    assert start_body["selected_plan_id"] is None
    assert start_body["plans"] == []
    assert start_body["action_count"] == 0
    _assert_progress(
        start_body,
        current_stage="planning_queries",
        stage_history=["understanding_request", "planning_queries"],
    )
    assert start_body["clarification"] == {
        "prompt": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
        "missing_fields": ["scenario_or_participants", "time_window"],
    }
    _assert_plan_version(
        start_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        start_body,
        current_stage="planning_queries",
        stage_history=["understanding_request", "planning_queries"],
    )
    source_run_id = UUID(start_body["run_id"])

    replan_response = test_client.post(
        f"/demo/runs/{source_run_id}/replan",
        json={
            "user_input": "今天下午一个人出门玩几个小时，别太远。",
            "selected_plan_index": 0,
        },
    )
    assert replan_response.status_code == 409

    clarify_response = test_client.post(
        f"/demo/runs/{source_run_id}/clarify",
        json={
            "user_input": "今天下午一个人出门玩几个小时，别太远。",
            "selected_plan_index": 0,
        },
    )

    assert clarify_response.status_code == 200
    clarify_body = clarify_response.json()
    _assert_no_forbidden_keys(clarify_body)
    _assert_public_run_redaction(clarify_body)
    assert UUID(clarify_body["run_id"]) != source_run_id
    assert clarify_body["status"] == "awaiting_confirmation"
    assert clarify_body["clarification"] is None
    assert clarify_body["selected_plan_id"] is not None
    assert clarify_body["plans"]
    _assert_plan_version(
        clarify_body,
        version_number=1,
        source_run_id=str(source_run_id),
        source_selected_plan_id=None,
    )
    _assert_progress(
        clarify_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    _assert_progress(
        clarify_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )

    db = SessionLocal()
    try:
        source_run = _load_run(db, source_run_id)
        clarified_run = _load_run(db, UUID(clarify_body["run_id"]))
        assert clarified_run.user_id == source_run.user_id
        assert clarified_run.session_id == source_run.session_id
        turns = list(
            db.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == source_run.session_id)
                .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
            ).all()
        )
        assert [turn.turn_type for turn in turns] == [
            "user_request",
            "assistant_clarification_request",
            "user_clarification_reply",
            "assistant_plan_options",
        ]
        assert turns[1].run_id == source_run.run_id
        assert turns[1].payload_json == {
            "missing_fields": ["scenario_or_participants", "time_window"],
            "run_status": "awaiting_clarification",
        }
        _assert_turn_snapshot(
            turns[0],
            run_id=source_run.run_id,
            run_status="awaiting_clarification",
            plan_version_label="v1",
            clarification_missing_fields=["scenario_or_participants", "time_window"],
            selected_plan_id=None,
            plan_count=0,
        )
        _assert_turn_snapshot(
            turns[1],
            run_id=source_run.run_id,
            run_status="awaiting_clarification",
            plan_version_label="v1",
            clarification_missing_fields=["scenario_or_participants", "time_window"],
            selected_plan_id=None,
            plan_count=0,
        )
        assert turns[2].run_id == clarified_run.run_id
        assert turns[2].payload_json == {
            "mode": "clarify",
            "source_run_id": str(source_run.run_id),
            "source_missing_fields": ["scenario_or_participants", "time_window"],
        }
        assert turns[3].run_id == clarified_run.run_id
        _assert_turn_snapshot(
            turns[2],
            run_id=clarified_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v1",
            clarification_missing_fields=[],
            selected_plan_id=clarify_body["selected_plan_id"],
            plan_count=len(clarify_body["plans"]),
        )
        _assert_turn_snapshot(
            turns[3],
            run_id=clarified_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v1",
            clarification_missing_fields=[],
            selected_plan_id=clarify_body["selected_plan_id"],
            plan_count=len(clarify_body["plans"]),
        )
        assert source_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 1,
            "source_run_id": None,
            "source_selected_plan_id": None,
        }
        assert clarified_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 1,
            "source_run_id": str(source_run.run_id),
            "source_selected_plan_id": None,
        }
        assert source_run.metadata_json["workflow"]["clarification"] == {
            "policy_version": "clarification_policy_v0",
            "missing_fields": ["scenario_or_participants", "time_window"],
            "question_text": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
        }
    finally:
        db.close()


def test_conversation_clarify_replan_manifest_confirm_closure(client) -> None:
    test_client, case_ids, external_user_ids = client
    payload = _start_payload(case_ids, external_user_ids)
    payload["user_input"] = VAGUE_USER_INPUT
    payload["mock_world_profile"] = "solo_afternoon"

    start_response = test_client.post("/demo/runs", json=payload)

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_clarification"
    assert start_body["plans"] == []
    assert start_body["selected_plan_id"] is None
    assert start_body["action_count"] == 0
    assert start_body["clarification"] is not None
    _assert_plan_version(
        start_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    source_run_id = UUID(start_body["run_id"])

    clarify_response = test_client.post(
        f"/demo/runs/{source_run_id}/clarify",
        json={
            "user_input": "This afternoon I want a nearby solo outing for a few hours.",
            "selected_plan_index": 0,
        },
    )

    assert clarify_response.status_code == 200
    clarify_body = clarify_response.json()
    _assert_no_forbidden_keys(clarify_body)
    _assert_public_run_redaction(clarify_body)
    assert clarify_body["status"] == "awaiting_confirmation"
    assert clarify_body["selected_plan_id"] is not None
    assert len(clarify_body["plans"]) >= 2, "closure regression requires a non-default source plan"
    _assert_plan_version(
        clarify_body,
        version_number=1,
        source_run_id=str(source_run_id),
        source_selected_plan_id=None,
    )
    clarified_run_id = UUID(clarify_body["run_id"])
    source_plan_index = 1
    source_plan_id = clarify_body["plans"][source_plan_index]["plan_id"]

    db = SessionLocal()
    try:
        assert _count_actions(db, source_run_id) == 0
        assert _count_actions(db, clarified_run_id) == 0
        assert _count_write_tool_events(db, source_run_id) == 0
        assert _count_write_tool_events(db, clarified_run_id) == 0
    finally:
        db.close()

    replan_response = test_client.post(
        f"/demo/runs/{clarified_run_id}/replan",
        json={
            "user_input": "Keep it nearby, but make it indoor this time.",
            "selected_plan_index": source_plan_index,
        },
    )

    assert replan_response.status_code == 200
    replan_body = replan_response.json()
    _assert_no_forbidden_keys(replan_body)
    _assert_public_run_redaction(replan_body)
    assert replan_body["status"] == "awaiting_confirmation"
    assert replan_body["selected_plan_id"] is not None
    _assert_plan_version(
        replan_body,
        version_number=2,
        source_run_id=str(clarified_run_id),
        source_selected_plan_id=source_plan_id,
    )
    replan_run_id = UUID(replan_body["run_id"])
    selected_replan_plan = next(plan for plan in replan_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(selected_replan_plan)
    manifest = selected_replan_plan["action_manifest"]
    assert manifest["source"] == "proposed_actions"
    assert manifest["action_count"] >= 1
    assert len(manifest["actions"]) >= 1
    for action in manifest["actions"]:
        assert action["execution_order"] is not None
        assert action["action_type"]
        assert action["target_id"]

    db = SessionLocal()
    try:
        assert _count_actions(db, source_run_id) == 0
        assert _count_actions(db, clarified_run_id) == 0
        assert _count_actions(db, replan_run_id) == 0
        assert _count_write_tool_events(db, source_run_id) == 0
        assert _count_write_tool_events(db, clarified_run_id) == 0
        assert _count_write_tool_events(db, replan_run_id) == 0
    finally:
        db.close()

    confirm_response = test_client.post(
        f"/demo/runs/{replan_run_id}/confirm",
        json={"confirmed_by": "conversation-closure-test"},
    )

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    _assert_no_forbidden_keys(confirm_body)
    _assert_public_run_redaction(confirm_body)
    assert confirm_body["run_id"] == str(replan_run_id)
    assert confirm_body["status"] == "completed"
    assert confirm_body["execution_status"] == "succeeded"
    assert confirm_body["feedback_status"] == "completed"
    assert confirm_body["action_count"] > 0
    _assert_plan_version(
        confirm_body,
        version_number=2,
        source_run_id=str(clarified_run_id),
        source_selected_plan_id=source_plan_id,
    )
    selected_confirmed_plan = next(plan for plan in confirm_body["plans"] if plan["selected"])
    _assert_action_manifest_confirmed(selected_confirmed_plan)

    db = SessionLocal()
    try:
        source_run = _load_run(db, source_run_id)
        clarified_run = _load_run(db, clarified_run_id)
        replan_run = _load_run(db, replan_run_id)
        assert source_run.status == "awaiting_clarification"
        assert clarified_run.status == "awaiting_confirmation"
        assert replan_run.status == "completed"
        assert _count_actions(db, source_run_id) == 0
        assert _count_actions(db, clarified_run_id) == 0
        assert _count_actions(db, replan_run_id) == confirm_body["action_count"]
        assert replan_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 2,
            "source_run_id": str(clarified_run_id),
            "source_selected_plan_id": source_plan_id,
        }
    finally:
        db.close()

    for run_id, expected_status, expected_version in [
        (source_run_id, "awaiting_clarification", 1),
        (clarified_run_id, "awaiting_confirmation", 1),
        (replan_run_id, "completed", 2),
    ]:
        readback_response = test_client.get(f"/demo/runs/{run_id}")
        assert readback_response.status_code == 200
        readback_body = readback_response.json()
        _assert_no_forbidden_keys(readback_body)
        _assert_public_run_redaction(readback_body)
        assert readback_body["status"] == expected_status
        assert readback_body["plan_version"]["version_label"] == f"v{expected_version}"
        for private_key in {
            "session_id",
            "conversation",
            "tool_events",
            "tool_event_count",
            "node_history",
            "trace",
            "trace_id",
            "agent_roles",
            "observability_status",
        }:
            assert private_key not in readback_body


def test_demo_run_recovery_clarification_flow_reuses_public_clarify_contract(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_review = DeterministicValidatorRecoveryAgent.review
    call_count = {"count": 0}

    def _ask_then_restore(
        self,
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
        recovery_context=None,
        context=None,
    ):
        call_count["count"] += 1
        if call_count["count"] > 1:
            return original_review(
                self,
                plan,
                enrichment,
                drafts,
                pre_confirmation_action_count=pre_confirmation_action_count,
                recovery_context=recovery_context,
                context=context,
            )

        failed_check = ReviewCheck(
            check_name="draft_exists",
            status="failed",
            severity="error",
            message="Need distance flexibility.",
        )
        review = FinalReviewResult(
            run_id=drafts.run_id,
            provider_profile=drafts.provider_profile,
            decision="blocked",
            safe_to_present=False,
            checks=[failed_check],
            errors=[failed_check],
            gate_version="test-gate",
        )
        decision = RecoveryDecision(
            verdict="failed",
            error_type="draft_exists",
            recovery_action="ask_user",
            retry_budget=0,
            reason="Need distance flexibility.",
        )
        return (
            AgentResult(
                role="validator_recovery",
                status="blocked",
                summary="Need distance flexibility.",
                adapter_version="test-validator",
                output_json={"recovery_decision": decision.model_dump(mode="json")},
            ),
            review,
            decision,
        )

    monkeypatch.setattr(DeterministicValidatorRecoveryAgent, "review", _ask_then_restore)
    test_client, case_ids, external_user_ids = client

    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_clarification"
    assert start_body["selected_plan_id"] is None
    assert start_body["plans"] == []
    assert start_body["action_count"] == 0
    assert start_body["clarification"] == {
        "prompt": (
            "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
            "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
            "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
        ),
        "missing_fields": ["distance_flexibility"],
    }
    source_run_id = UUID(start_body["run_id"])

    clarify_response = test_client.post(
        f"/demo/runs/{source_run_id}/clarify",
        json={
            "user_input": "可以稍微远一点，但还是想要轻松一点、晚饭清淡一些。",
            "selected_plan_index": 0,
        },
    )

    assert clarify_response.status_code == 200
    clarify_body = clarify_response.json()
    _assert_no_forbidden_keys(clarify_body)
    _assert_public_run_redaction(clarify_body)
    assert UUID(clarify_body["run_id"]) != source_run_id
    assert clarify_body["status"] == "awaiting_confirmation"
    assert clarify_body["clarification"] is None
    assert clarify_body["selected_plan_id"] is not None
    _assert_plan_version(
        clarify_body,
        version_number=1,
        source_run_id=str(source_run_id),
        source_selected_plan_id=None,
    )

    db = SessionLocal()
    try:
        source_run = _load_run(db, source_run_id)
        clarified_run = _load_run(db, UUID(clarify_body["run_id"]))
        assert clarified_run.user_id == source_run.user_id
        assert clarified_run.session_id == source_run.session_id
        turns = list(
            db.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == source_run.session_id)
                .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
            ).all()
        )
        assert [turn.turn_type for turn in turns] == [
            "user_request",
            "assistant_clarification_request",
            "user_clarification_reply",
            "assistant_plan_options",
        ]
        assert turns[1].payload_json == {
            "missing_fields": ["distance_flexibility"],
            "run_status": "awaiting_clarification",
        }
        _assert_turn_snapshot(
            turns[0],
            run_id=source_run.run_id,
            run_status="awaiting_clarification",
            plan_version_label="v1",
            clarification_missing_fields=["distance_flexibility"],
            selected_plan_id=None,
            plan_count=0,
        )
        _assert_turn_snapshot(
            turns[1],
            run_id=source_run.run_id,
            run_status="awaiting_clarification",
            plan_version_label="v1",
            clarification_missing_fields=["distance_flexibility"],
            selected_plan_id=None,
            plan_count=0,
        )
        assert turns[2].payload_json == {
            "mode": "clarify",
            "source_run_id": str(source_run.run_id),
            "source_missing_fields": ["distance_flexibility"],
        }
        _assert_turn_snapshot(
            turns[2],
            run_id=clarified_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v1",
            clarification_missing_fields=[],
            selected_plan_id=clarify_body["selected_plan_id"],
            plan_count=len(clarify_body["plans"]),
        )
        _assert_turn_snapshot(
            turns[3],
            run_id=clarified_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v1",
            clarification_missing_fields=[],
            selected_plan_id=clarify_body["selected_plan_id"],
            plan_count=len(clarify_body["plans"]),
        )
        assert source_run.metadata_json["workflow"]["clarification"] == {
            "policy_version": "recovery_clarification_v1",
            "missing_fields": ["distance_flexibility"],
            "question_text": (
                "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
                "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
                "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
            ),
        }
    finally:
        db.close()


def test_demo_run_replan_reuses_session_and_returns_new_run(client) -> None:
    test_client, case_ids, external_user_ids = client
    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    source_body = start_response.json()
    source_run_id = UUID(source_body["run_id"])
    source_selected_plan_id = source_body["selected_plan_id"]
    source_selected_plan_index = next(
        index for index, plan in enumerate(source_body["plans"]) if plan["plan_id"] == source_selected_plan_id
    )
    _assert_plan_version(
        source_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    _assert_progress(
        source_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )

    replan_response = test_client.post(
        f"/demo/runs/{source_run_id}/replan",
        json={
            "user_input": "Keep it nearby, but make dinner lighter and stay flexible.",
            "selected_plan_index": source_selected_plan_index,
        },
    )

    assert replan_response.status_code == 200
    replan_body = replan_response.json()
    _assert_no_forbidden_keys(replan_body)
    _assert_public_run_redaction(replan_body)
    assert UUID(replan_body["run_id"]) != source_run_id
    assert replan_body["status"] == "awaiting_confirmation"
    assert "session_id" not in replan_body
    assert "conversation" not in replan_body
    _assert_plan_version(
        replan_body,
        version_number=2,
        source_run_id=str(source_run_id),
        source_selected_plan_id=source_selected_plan_id,
    )
    _assert_progress(
        replan_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    replan_selected_plan = next(plan for plan in replan_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(replan_selected_plan)

    second_replan_response = test_client.post(
        f"/demo/runs/{replan_body['run_id']}/replan",
        json={
            "user_input": "Keep it nearby again, but reduce walking even more.",
            "selected_plan_index": next(
                index for index, plan in enumerate(replan_body["plans"]) if plan["plan_id"] == replan_body["selected_plan_id"]
            ),
        },
    )

    assert second_replan_response.status_code == 200
    second_replan_body = second_replan_response.json()
    _assert_no_forbidden_keys(second_replan_body)
    _assert_public_run_redaction(second_replan_body)
    assert second_replan_body["run_id"] not in {str(source_run_id), replan_body["run_id"]}
    _assert_plan_version(
        second_replan_body,
        version_number=3,
        source_run_id=replan_body["run_id"],
        source_selected_plan_id=replan_body["selected_plan_id"],
    )
    _assert_progress(
        second_replan_body,
        current_stage="ready_for_confirmation",
        stage_history=READY_PROGRESS_HISTORY,
    )
    second_replan_selected_plan = next(plan for plan in second_replan_body["plans"] if plan["selected"])
    _assert_action_manifest_preview(second_replan_selected_plan)

    status_response = test_client.get(f"/demo/runs/{source_run_id}")
    assert status_response.status_code == 200
    source_after = status_response.json()
    assert source_after["run_id"] == str(source_run_id)
    assert source_after["status"] == source_body["status"]
    assert source_after["selected_plan_id"] == source_selected_plan_id
    assert source_after["plan_version"] == source_body["plan_version"]
    assert source_after["progress"] == source_body["progress"]

    first_replan_status_response = test_client.get(f"/demo/runs/{replan_body['run_id']}")
    assert first_replan_status_response.status_code == 200
    first_replan_after = first_replan_status_response.json()
    assert first_replan_after["run_id"] == replan_body["run_id"]
    assert first_replan_after["selected_plan_id"] == replan_body["selected_plan_id"]
    assert first_replan_after["plan_version"] == replan_body["plan_version"]
    assert first_replan_after["progress"] == replan_body["progress"]

    db = SessionLocal()
    try:
        source_run = _load_run(db, source_run_id)
        replan_run = _load_run(db, UUID(replan_body["run_id"]))
        second_replan_run = _load_run(db, UUID(second_replan_body["run_id"]))
        assert replan_run.user_id == source_run.user_id
        assert replan_run.session_id == source_run.session_id
        assert second_replan_run.user_id == source_run.user_id
        assert second_replan_run.session_id == source_run.session_id
        turns = list(
            db.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == source_run.session_id)
                .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
            ).all()
        )
        assert [turn.turn_type for turn in turns] == [
            "user_request",
            "assistant_plan_options",
            "user_follow_up",
            "assistant_replan_options",
            "user_follow_up",
            "assistant_replan_options",
        ]
        _assert_turn_snapshot(
            turns[0],
            run_id=source_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v1",
            clarification_missing_fields=[],
            selected_plan_id=source_body["selected_plan_id"],
            plan_count=len(source_body["plans"]),
        )
        _assert_turn_snapshot(
            turns[1],
            run_id=source_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v1",
            clarification_missing_fields=[],
            selected_plan_id=source_body["selected_plan_id"],
            plan_count=len(source_body["plans"]),
        )
        assert turns[2].run_id == replan_run.run_id
        assert turns[2].payload_json == {
            "mode": "replan",
            "source_run_id": str(source_run.run_id),
            "source_selected_plan_id": source_selected_plan_id,
        }
        assert turns[3].run_id == replan_run.run_id
        assert turns[3].payload_json == {
            "mode": "replan",
            "source_run_id": str(source_run.run_id),
            "selected_plan_id": replan_body["selected_plan_id"],
            "plan_ids": [plan["plan_id"] for plan in replan_body["plans"]],
            "plan_count": len(replan_body["plans"]),
            "run_status": "awaiting_confirmation",
        }
        _assert_turn_snapshot(
            turns[2],
            run_id=replan_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v2",
            clarification_missing_fields=[],
            selected_plan_id=replan_body["selected_plan_id"],
            plan_count=len(replan_body["plans"]),
        )
        _assert_turn_snapshot(
            turns[3],
            run_id=replan_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v2",
            clarification_missing_fields=[],
            selected_plan_id=replan_body["selected_plan_id"],
            plan_count=len(replan_body["plans"]),
        )
        assert turns[4].run_id == second_replan_run.run_id
        assert turns[4].payload_json == {
            "mode": "replan",
            "source_run_id": str(replan_run.run_id),
            "source_selected_plan_id": replan_body["selected_plan_id"],
        }
        assert turns[5].run_id == second_replan_run.run_id
        assert turns[5].payload_json == {
            "mode": "replan",
            "source_run_id": str(replan_run.run_id),
            "selected_plan_id": second_replan_body["selected_plan_id"],
            "plan_ids": [plan["plan_id"] for plan in second_replan_body["plans"]],
            "plan_count": len(second_replan_body["plans"]),
            "run_status": "awaiting_confirmation",
        }
        _assert_turn_snapshot(
            turns[4],
            run_id=second_replan_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v3",
            clarification_missing_fields=[],
            selected_plan_id=second_replan_body["selected_plan_id"],
            plan_count=len(second_replan_body["plans"]),
        )
        _assert_turn_snapshot(
            turns[5],
            run_id=second_replan_run.run_id,
            run_status="awaiting_confirmation",
            plan_version_label="v3",
            clarification_missing_fields=[],
            selected_plan_id=second_replan_body["selected_plan_id"],
            plan_count=len(second_replan_body["plans"]),
        )
        assert "draft" not in turns[3].payload_json
        assert "plan_json" not in turns[3].payload_json
        assert "draft" not in turns[5].payload_json
        assert "plan_json" not in turns[5].payload_json
        assert isinstance(replan_run.metadata_json, dict)
        assert replan_run.metadata_json["demo"]["conversation"]["mode"] == "follow_up_replan_v0"
        assert replan_run.metadata_json["demo"]["conversation"]["source_run_id"] == str(source_run.run_id)
        assert replan_run.metadata_json["demo"]["conversation"]["source_selected_plan_id"] == source_selected_plan_id
        assert source_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 1,
            "source_run_id": None,
            "source_selected_plan_id": None,
        }
        assert replan_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 2,
            "source_run_id": str(source_run.run_id),
            "source_selected_plan_id": source_selected_plan_id,
        }
        assert second_replan_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 3,
            "source_run_id": str(replan_run.run_id),
            "source_selected_plan_id": replan_body["selected_plan_id"],
        }
    finally:
        db.close()
