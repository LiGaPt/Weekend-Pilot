from __future__ import annotations

from backend.app.demo.action_manifest import summarize_action_manifest
from backend.app.demo.service import sanitize_demo_payload


def test_uses_proposed_actions_with_one_based_execution_order() -> None:
    summary = summarize_action_manifest(
        {
            "draft": {
                "proposed_actions": [
                    {
                        "action_ref": "draft_1_action_1",
                        "action_type": "book_ticket",
                        "target_id": "activity_museum_001",
                        "payload": {"poi_id": "activity_museum_001", "quantity": 3},
                        "requires_confirmation": True,
                        "reason": "Confirm to lock entry.",
                    },
                    {
                        "action_ref": "draft_1_action_2",
                        "action_type": "reserve_restaurant",
                        "target_id": "restaurant_light_001",
                        "payload": {"restaurant_id": "restaurant_light_001", "party_size": 3},
                        "requires_confirmation": True,
                        "reason": "Confirm to lock dinner seating.",
                    },
                ]
            }
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "proposed_actions"
    assert summary.action_count == 2
    assert [item.execution_order for item in summary.actions] == [1, 2]
    assert [item.action_type for item in summary.actions] == ["book_ticket", "reserve_restaurant"]


def test_uses_confirmed_actions_with_stored_execution_order() -> None:
    summary = summarize_action_manifest(
        {
            "confirmed_actions": [
                {
                    "action_ref": "draft_1_action_2",
                    "execution_order": 2,
                    "tool_name": "reserve_restaurant",
                    "target_id": "restaurant_light_001",
                    "payload": {"restaurant_id": "restaurant_light_001", "party_size": 3},
                    "idempotency_key": "internal-key-2",
                    "user_confirmed": True,
                    "reason": "Confirm to lock dinner seating.",
                },
                {
                    "action_ref": "draft_1_action_1",
                    "execution_order": 1,
                    "tool_name": "book_ticket",
                    "target_id": "activity_museum_001",
                    "payload": {"poi_id": "activity_museum_001", "quantity": 3},
                    "idempotency_key": "internal-key-1",
                    "user_confirmed": True,
                    "reason": "Confirm to lock entry.",
                },
            ]
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "confirmed_actions"
    assert summary.action_count == 2
    assert [item.execution_order for item in summary.actions] == [1, 2]
    assert [item.action_type for item in summary.actions] == ["book_ticket", "reserve_restaurant"]


def test_malformed_confirmed_actions_falls_back_to_proposed_actions() -> None:
    summary = summarize_action_manifest(
        {
            "draft": {
                "proposed_actions": [
                    {
                        "action_ref": "draft_1_action_1",
                        "action_type": "join_queue",
                        "target_id": "queue_restaurant_light_001",
                        "payload": {"queue_id": "queue_restaurant_light_001", "party_size": 3},
                        "requires_confirmation": True,
                        "reason": "Confirm to join the queue.",
                    }
                ]
            },
            "confirmed_actions": [
                {
                    "action_ref": "draft_1_action_1",
                    "execution_order": 1,
                    "target_id": "queue_restaurant_light_001",
                    "payload": {"queue_id": "queue_restaurant_light_001", "party_size": 3},
                    "reason": "Missing tool name should invalidate confirmed source.",
                }
            ],
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "proposed_actions"
    assert summary.action_count == 1
    assert summary.actions[0].action_type == "join_queue"


def test_duplicate_confirmed_execution_order_falls_back_to_proposed_actions() -> None:
    summary = summarize_action_manifest(
        {
            "draft": {
                "proposed_actions": [
                    {
                        "action_ref": "draft_1_action_1",
                        "action_type": "reserve_restaurant",
                        "target_id": "restaurant_light_001",
                        "payload": {"restaurant_id": "restaurant_light_001", "party_size": 3},
                        "requires_confirmation": True,
                        "reason": "Confirm to lock dinner seating.",
                    }
                ]
            },
            "confirmed_actions": [
                {
                    "action_ref": "draft_1_action_1",
                    "execution_order": 1,
                    "tool_name": "reserve_restaurant",
                    "target_id": "restaurant_light_001",
                    "payload": {"restaurant_id": "restaurant_light_001", "party_size": 3},
                    "reason": "First confirmed action.",
                },
                {
                    "action_ref": "draft_1_action_2",
                    "execution_order": 1,
                    "tool_name": "book_ticket",
                    "target_id": "activity_museum_001",
                    "payload": {"poi_id": "activity_museum_001", "quantity": 3},
                    "reason": "Duplicate execution order should invalidate confirmed source.",
                },
            ],
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "proposed_actions"
    assert summary.action_count == 1
    assert summary.actions[0].action_type == "reserve_restaurant"


def test_non_mapping_confirmed_item_falls_back_to_proposed_actions() -> None:
    summary = summarize_action_manifest(
        {
            "draft": {
                "proposed_actions": [
                    {
                        "action_ref": "draft_1_action_1",
                        "action_type": "join_queue",
                        "target_id": "queue_restaurant_light_001",
                        "payload": {"queue_id": "queue_restaurant_light_001", "party_size": 3},
                        "requires_confirmation": True,
                        "reason": "Confirm to join the queue.",
                    }
                ]
            },
            "confirmed_actions": [
                {
                    "action_ref": "draft_1_action_1",
                    "execution_order": 1,
                    "tool_name": "join_queue",
                    "target_id": "queue_restaurant_light_001",
                    "payload": {"queue_id": "queue_restaurant_light_001", "party_size": 3},
                    "reason": "Valid entry.",
                },
                "bad-item",
            ],
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "proposed_actions"
    assert summary.action_count == 1
    assert summary.actions[0].action_type == "join_queue"


def test_returns_none_when_no_valid_action_source_exists() -> None:
    summary = summarize_action_manifest(
        {
            "draft": {
                "proposed_actions": "bad-actions",
            }
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "none"
    assert summary.action_count == 0
    assert summary.actions == []


def test_non_mapping_proposed_action_returns_none() -> None:
    summary = summarize_action_manifest(
        {
            "draft": {
                "proposed_actions": [
                    {
                        "action_ref": "draft_1_action_1",
                        "action_type": "join_queue",
                        "target_id": "queue_restaurant_light_001",
                        "payload": {"queue_id": "queue_restaurant_light_001", "party_size": 3},
                        "requires_confirmation": True,
                        "reason": "Confirm to join the queue.",
                    },
                    "bad-item",
                ],
            }
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "none"
    assert summary.action_count == 0
    assert summary.actions == []


def test_payload_preview_removes_internal_execution_fields() -> None:
    summary = summarize_action_manifest(
        {
            "confirmed_actions": [
                {
                    "action_ref": "draft_1_action_1",
                    "execution_order": 1,
                    "tool_name": "book_ticket",
                    "target_id": "activity_museum_001",
                    "payload": {
                        "poi_id": "activity_museum_001",
                        "idempotency_key": "nested-internal-key",
                        "nested": {"action_id": "internal-action"},
                    },
                    "idempotency_key": "top-level-internal-key",
                    "user_confirmed": True,
                    "reason": "Confirm to lock entry.",
                }
            ]
        },
        sanitizer=sanitize_demo_payload,
    )

    assert summary.source == "confirmed_actions"
    assert summary.actions[0].payload_preview == {
        "poi_id": "activity_museum_001",
        "nested": {},
    }
