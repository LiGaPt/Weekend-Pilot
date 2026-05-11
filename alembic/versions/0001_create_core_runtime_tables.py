"""create core runtime tables

Revision ID: 0001_create_core_runtime_tables
Revises:
Create Date: 2026-05-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_create_core_runtime_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
        sa.UniqueConstraint("external_id", name=op.f("uq_users_external_id")),
    )
    op.create_index(op.f("ix_users_external_id"), "users", ["external_id"], unique=False)

    op.create_table(
        "user_profiles",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferences_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraints_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_user_profiles_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id", name=op.f("pk_user_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_profiles_user_id")),
    )
    op.create_index(op.f("ix_user_profiles_user_id"), "user_profiles", ["user_id"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_id", sa.String(length=128), nullable=True),
        sa.Column("agent_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("tool_profile", sa.String(length=64), nullable=False),
        sa.Column("world_profile", sa.String(length=64), nullable=False),
        sa.Column("failure_profile", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_agent_runs_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_agent_runs")),
    )
    op.create_index(op.f("ix_agent_runs_case_id"), "agent_runs", ["case_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)
    op.create_index(op.f("ix_agent_runs_user_id"), "agent_runs", ["user_id"], unique=False)

    op.create_table(
        "memory_items",
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_langsmith_trace_id", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.run_id"], name=op.f("fk_memory_items_source_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_memory_items_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("memory_id", name=op.f("pk_memory_items")),
        sa.UniqueConstraint("user_id", "memory_type", "key", name=op.f("uq_memory_items_user_id")),
    )
    op.create_index(op.f("ix_memory_items_expires_at"), "memory_items", ["expires_at"], unique=False)
    op.create_index(op.f("ix_memory_items_memory_type"), "memory_items", ["memory_type"], unique=False)
    op.create_index(op.f("ix_memory_items_source_run_id"), "memory_items", ["source_run_id"], unique=False)
    op.create_index(op.f("ix_memory_items_status"), "memory_items", ["status"], unique=False)
    op.create_index(op.f("ix_memory_items_user_id"), "memory_items", ["user_id"], unique=False)

    op.create_table(
        "plans",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("selected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], name=op.f("fk_plans_run_id_agent_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_id", name=op.f("pk_plans")),
    )
    op.create_index(op.f("ix_plans_run_id"), "plans", ["run_id"], unique=False)
    op.create_index(op.f("ix_plans_status"), "plans", ["status"], unique=False)

    op.create_table(
        "tool_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("langsmith_trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], name=op.f("fk_tool_events_run_id_agent_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_tool_events")),
    )
    op.create_index(op.f("ix_tool_events_langsmith_trace_id"), "tool_events", ["langsmith_trace_id"], unique=False)
    op.create_index(op.f("ix_tool_events_run_id"), "tool_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_tool_events_status"), "tool_events", ["status"], unique=False)
    op.create_index(op.f("ix_tool_events_tool_name"), "tool_events", ["tool_name"], unique=False)

    op.create_table(
        "action_ledger",
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], name=op.f("fk_action_ledger_run_id_agent_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("action_id", name=op.f("pk_action_ledger")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_action_ledger_idempotency_key")),
    )
    op.create_index(op.f("ix_action_ledger_action_type"), "action_ledger", ["action_type"], unique=False)
    op.create_index(op.f("ix_action_ledger_run_id"), "action_ledger", ["run_id"], unique=False)
    op.create_index(op.f("ix_action_ledger_status"), "action_ledger", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_action_ledger_status"), table_name="action_ledger")
    op.drop_index(op.f("ix_action_ledger_run_id"), table_name="action_ledger")
    op.drop_index(op.f("ix_action_ledger_action_type"), table_name="action_ledger")
    op.drop_table("action_ledger")

    op.drop_index(op.f("ix_tool_events_tool_name"), table_name="tool_events")
    op.drop_index(op.f("ix_tool_events_status"), table_name="tool_events")
    op.drop_index(op.f("ix_tool_events_run_id"), table_name="tool_events")
    op.drop_index(op.f("ix_tool_events_langsmith_trace_id"), table_name="tool_events")
    op.drop_table("tool_events")

    op.drop_index(op.f("ix_plans_status"), table_name="plans")
    op.drop_index(op.f("ix_plans_run_id"), table_name="plans")
    op.drop_table("plans")

    op.drop_index(op.f("ix_memory_items_user_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_status"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_source_run_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_memory_type"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_expires_at"), table_name="memory_items")
    op.drop_table("memory_items")

    op.drop_index(op.f("ix_agent_runs_user_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_case_id"), table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index(op.f("ix_user_profiles_user_id"), table_name="user_profiles")
    op.drop_table("user_profiles")

    op.drop_index(op.f("ix_users_external_id"), table_name="users")
    op.drop_table("users")
