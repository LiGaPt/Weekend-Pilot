"""add conversation turn trace snapshots

Revision ID: 0004_turn_trace_snap_v0
Revises: 0003_memory_userctl_v0
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_turn_trace_snap_v0"
down_revision: str | None = "0003_memory_userctl_v0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation_turns", sa.Column("trace_id", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_conversation_turns_trace_id"), "conversation_turns", ["trace_id"], unique=False)
    op.add_column(
        "conversation_turns",
        sa.Column(
            "state_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute("UPDATE conversation_turns SET state_snapshot_json = '{}'::jsonb WHERE state_snapshot_json IS NULL")
    op.alter_column("conversation_turns", "state_snapshot_json", nullable=False)


def downgrade() -> None:
    op.drop_column("conversation_turns", "state_snapshot_json")
    op.drop_index(op.f("ix_conversation_turns_trace_id"), table_name="conversation_turns")
    op.drop_column("conversation_turns", "trace_id")
