from __future__ import annotations

import backend.app.planning as planning
from backend.app.planning import DeterministicIntentParser


def test_clarification_policy_blocks_missing_scenario_and_time() -> None:
    intent = DeterministicIntentParser().parse("想周末出去玩一下。")

    assert hasattr(planning, "apply_clarification_policy")
    summary = planning.apply_clarification_policy(intent)

    assert summary is not None
    assert summary.policy_version == "clarification_policy_v0"
    assert summary.missing_fields == ["scenario_or_participants", "time_window"]
    assert summary.question_text == "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。"


def test_clarification_policy_blocks_missing_time_only() -> None:
    intent = DeterministicIntentParser().parse("一个人出去玩。")

    assert hasattr(planning, "apply_clarification_policy")
    summary = planning.apply_clarification_policy(intent)

    assert summary is not None
    assert summary.missing_fields == ["time_window"]
    assert summary.question_text == "为了继续规划，请补充大概什么时间出发、准备玩多久。"


def test_clarification_policy_blocks_missing_scenario_only() -> None:
    intent = DeterministicIntentParser().parse("今天下午出去玩几个小时。")

    assert hasattr(planning, "apply_clarification_policy")
    summary = planning.apply_clarification_policy(intent)

    assert summary is not None
    assert summary.missing_fields == ["scenario_or_participants"]
    assert summary.question_text == "为了继续规划，请补充这次是谁一起去。"


def test_clarification_policy_returns_none_for_specific_request() -> None:
    intent = DeterministicIntentParser().parse("今天下午一个人出门玩几个小时，别太远。")

    assert hasattr(planning, "apply_clarification_policy")
    summary = planning.apply_clarification_policy(intent)

    assert summary is None
