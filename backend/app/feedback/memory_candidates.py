from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Literal

from pydantic import BaseModel


FeedbackMemoryCandidateKey = Literal["activity_style", "spouse_lighter_meals"]


class FeedbackMemoryCandidate(BaseModel):
    memory_type: str = "preference"
    key: FeedbackMemoryCandidateKey
    value_json: dict[str, Any]
    text: str | None = None
    confidence: Decimal = Decimal("0.6000")
    status: str = "candidate"
    expires_at: str | None = None


def extract_feedback_memory_candidates(plan_json: dict[str, Any]) -> list[FeedbackMemoryCandidate]:
    draft = plan_json.get("draft")
    if not isinstance(draft, dict):
        return []

    candidates: list[FeedbackMemoryCandidate] = []
    activity = draft.get("activity")
    if isinstance(activity, dict):
        activity_candidate = _activity_candidate(activity)
        if activity_candidate is not None:
            candidates.append(activity_candidate)

    dining = draft.get("dining")
    if isinstance(dining, dict):
        dining_candidate = _dining_candidate(dining)
        if dining_candidate is not None:
            candidates.append(dining_candidate)

    return candidates


def _activity_candidate(activity: dict[str, Any]) -> FeedbackMemoryCandidate | None:
    tags = _string_tags(activity.get("tags"))
    preference = None
    for tag in ("citywalk", "indoor", "outdoor"):
        if tag in tags:
            preference = tag
            break
    if preference is None:
        return None
    return _candidate("activity_style", preference)


def _dining_candidate(dining: dict[str, Any]) -> FeedbackMemoryCandidate | None:
    tags = _string_tags(dining.get("tags"))
    if "lighter_options" not in tags:
        return None
    return _candidate("spouse_lighter_meals", "lighter_options")


def _candidate(key: FeedbackMemoryCandidateKey, preference: str) -> FeedbackMemoryCandidate:
    return FeedbackMemoryCandidate(
        key=key,
        value_json={
            "preference": preference,
            "source": "feedback_writer_v0",
            "evidence": "selected_candidate_tags",
        },
    )


def _string_tags(value: Any) -> set[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return set()
    tags = set()
    for item in value:
        if isinstance(item, str) and item:
            tags.add(item)
    return tags
