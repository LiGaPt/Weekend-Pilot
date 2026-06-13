from __future__ import annotations

from backend.app.feedback.memory_candidates import extract_feedback_memory_candidates


def _plan_json(*, activity_tags: list[str] | None = None, dining_tags: list[str] | None = None) -> dict:
    return {
        "schema_version": "reviewed_plan_v1",
        "draft": {
            "activity": {
                "candidate_id": "activity_1",
                "name": "Activity",
                "tags": activity_tags or [],
                "address": "100 Mock Science Road",
                "phone": "13800000000",
                "secret_token": "do-not-store",
            },
            "dining": {
                "candidate_id": "dining_1",
                "name": "Dining",
                "tags": dining_tags or [],
                "address": "8 Mock Dining Street",
                "authorization": "Bearer token",
            },
            "evidence": {
                "post_confirmation_message": {
                    "message_preview": "Call me at 13800000000",
                    "debug_trace": "hidden",
                }
            },
        },
        "feedback": {
            "headline": "completed",
            "final_arrangement_message": "Meet at 100 Mock Science Road",
            "next_steps": ["Bring token 123"],
        },
    }


def test_extract_feedback_memory_candidates_prioritizes_citywalk_over_outdoor() -> None:
    candidates = extract_feedback_memory_candidates(
        _plan_json(activity_tags=["outdoor", "citywalk"], dining_tags=[])
    )

    assert len(candidates) == 1
    assert candidates[0].key == "activity_style"
    assert candidates[0].value_json == {
        "preference": "citywalk",
        "source": "feedback_writer_v0",
        "evidence": "selected_candidate_tags",
    }
    assert candidates[0].text is None
    assert candidates[0].status == "candidate"


def test_extract_feedback_memory_candidates_emits_lighter_meals_from_dining_tags() -> None:
    candidates = extract_feedback_memory_candidates(
        _plan_json(activity_tags=["indoor"], dining_tags=["lighter_options", "quiet"])
    )

    assert [candidate.key for candidate in candidates] == [
        "activity_style",
        "spouse_lighter_meals",
    ]
    assert candidates[1].value_json == {
        "preference": "lighter_options",
        "source": "feedback_writer_v0",
        "evidence": "selected_candidate_tags",
    }


def test_extract_feedback_memory_candidates_returns_empty_without_supported_tags() -> None:
    assert extract_feedback_memory_candidates(_plan_json()) == []


def test_extract_feedback_memory_candidates_excludes_sensitive_and_address_like_fields() -> None:
    candidates = extract_feedback_memory_candidates(
        _plan_json(activity_tags=["indoor"], dining_tags=["lighter_options"])
    )

    serialized = str([candidate.model_dump(mode="json") for candidate in candidates])
    assert "100 Mock Science Road" not in serialized
    assert "13800000000" not in serialized
    assert "do-not-store" not in serialized
    assert "Bearer token" not in serialized
    assert "debug_trace" not in serialized
    assert all(candidate.text is None for candidate in candidates)
