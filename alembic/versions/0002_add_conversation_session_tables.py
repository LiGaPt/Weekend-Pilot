"""add conversation session tables

Revision ID: 0002_conversation_sessions_v0
Revises: 0001_create_core_runtime_tables
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_conversation_sessions_v0"
down_revision: str | None = "0001_create_core_runtime_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_conversation_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_conversation_sessions")),
    )
    op.create_index(op.f("ix_conversation_sessions_status"), "conversation_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_conversation_sessions_user_id"), "conversation_sessions", ["user_id"], unique=False)

    op.add_column("agent_runs", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_agent_runs_session_id_conversation_sessions"),
        "agent_runs",
        "conversation_sessions",
        ["session_id"],
        ["session_id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_agent_runs_session_id"), "agent_runs", ["session_id"], unique=False)

    op.create_table(
        "conversation_turns",
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("speaker_role", sa.String(length=32), nullable=False),
        sa.Column("turn_type", sa.String(length=64), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.run_id"],
            name=op.f("fk_conversation_turns_run_id_agent_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["conversation_sessions.session_id"],
            name=op.f("fk_conversation_turns_session_id_conversation_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("turn_id", name=op.f("pk_conversation_turns")),
        sa.UniqueConstraint("session_id", "turn_index", name=op.f("uq_conversation_turns_session_id")),
    )
    op.create_index(op.f("ix_conversation_turns_run_id"), "conversation_turns", ["run_id"], unique=False)
    op.create_index(op.f("ix_conversation_turns_session_id"), "conversation_turns", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_turns_session_id"), table_name="conversation_turns")
    op.drop_index(op.f("ix_conversation_turns_run_id"), table_name="conversation_turns")
    op.drop_table("conversation_turns")

    op.drop_index(op.f("ix_agent_runs_session_id"), table_name="agent_runs")
    op.drop_constraint(op.f("fk_agent_runs_session_id_conversation_sessions"), "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "session_id")

    op.drop_index(op.f("ix_conversation_sessions_user_id"), table_name="conversation_sessions")
    op.drop_index(op.f("ix_conversation_sessions_status"), table_name="conversation_sessions")
    op.drop_table("conversation_sessions")
