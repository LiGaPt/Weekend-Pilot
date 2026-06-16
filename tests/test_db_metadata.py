from sqlalchemy import UniqueConstraint

from backend.app.db.base import Base
from backend.app.models import runtime  # noqa: F401


EXPECTED_TABLES = {
    "users",
    "user_profiles",
    "memory_items",
    "agent_runs",
    "plans",
    "tool_events",
    "action_ledger",
    "conversation_sessions",
    "conversation_turns",
}


EXPECTED_COLUMNS = {
    "users": {"user_id", "external_id", "display_name", "created_at", "updated_at"},
    "user_profiles": {
        "profile_id",
        "user_id",
        "preferences_json",
        "constraints_json",
        "created_at",
        "updated_at",
    },
    "agent_runs": {
        "run_id",
        "user_id",
        "session_id",
        "case_id",
        "agent_version",
        "prompt_version",
        "tool_profile",
        "world_profile",
        "failure_profile",
        "status",
        "metadata_json",
        "created_at",
        "updated_at",
    },
    "conversation_sessions": {
        "session_id",
        "user_id",
        "channel",
        "status",
        "metadata_json",
        "created_at",
        "updated_at",
    },
    "conversation_turns": {
        "turn_id",
        "session_id",
        "run_id",
        "trace_id",
        "turn_index",
        "speaker_role",
        "turn_type",
        "content_text",
        "payload_json",
        "state_snapshot_json",
        "created_at",
    },
    "memory_items": {
        "memory_id",
        "user_id",
        "memory_type",
        "key",
        "value_json",
        "metadata_json",
        "text",
        "confidence",
        "source_run_id",
        "source_langsmith_trace_id",
        "last_used_at",
        "expires_at",
        "status",
        "created_at",
        "updated_at",
    },
    "plans": {"plan_id", "run_id", "status", "plan_json", "selected", "created_at", "updated_at"},
    "tool_events": {
        "event_id",
        "run_id",
        "tool_name",
        "tool_type",
        "provider",
        "request_json",
        "response_json",
        "error_json",
        "status",
        "cache_hit",
        "latency_ms",
        "langsmith_trace_id",
        "created_at",
    },
    "action_ledger": {
        "action_id",
        "run_id",
        "action_type",
        "target_id",
        "idempotency_key",
        "status",
        "request_json",
        "response_json",
        "error_json",
        "created_at",
        "updated_at",
    },
}


EXPECTED_FOREIGN_KEYS = {
    ("user_profiles", "user_id", "users", "user_id"),
    ("agent_runs", "user_id", "users", "user_id"),
    ("agent_runs", "session_id", "conversation_sessions", "session_id"),
    ("conversation_sessions", "user_id", "users", "user_id"),
    ("conversation_turns", "session_id", "conversation_sessions", "session_id"),
    ("conversation_turns", "run_id", "agent_runs", "run_id"),
    ("memory_items", "user_id", "users", "user_id"),
    ("memory_items", "source_run_id", "agent_runs", "run_id"),
    ("plans", "run_id", "agent_runs", "run_id"),
    ("tool_events", "run_id", "agent_runs", "run_id"),
    ("action_ledger", "run_id", "agent_runs", "run_id"),
}


def test_runtime_metadata_includes_core_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_runtime_tables_include_contract_columns() -> None:
    for table_name, column_names in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) >= column_names


def test_action_ledger_idempotency_key_is_unique() -> None:
    table = Base.metadata.tables["action_ledger"]
    unique_constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    unique_index_columns = {
        tuple(column.name for column in index.columns)
        for index in table.indexes
        if index.unique
    }

    assert ("idempotency_key",) in unique_constraint_columns | unique_index_columns


def test_conversation_turn_index_is_unique_per_session() -> None:
    table = Base.metadata.tables["conversation_turns"]
    unique_constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("session_id", "turn_index") in unique_constraint_columns


def test_representative_foreign_keys_are_defined() -> None:
    foreign_keys = {
        (
            table.name,
            fk.parent.name,
            fk.column.table.name,
            fk.column.name,
        )
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
    }

    assert EXPECTED_FOREIGN_KEYS <= foreign_keys


def test_conversation_turn_trace_id_is_indexed() -> None:
    table = Base.metadata.tables["conversation_turns"]
    indexed_columns = {
        tuple(column.name for column in index.columns)
        for index in table.indexes
    }

    assert ("trace_id",) in indexed_columns
