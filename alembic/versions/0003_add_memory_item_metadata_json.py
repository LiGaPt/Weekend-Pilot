"""add memory item metadata json

Revision ID: 0003_add_memory_item_metadata_json
Revises: 0002_add_conversation_session_tables
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_memory_userctl_v0"
down_revision: str | None = "0002_conversation_sessions_v0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute("UPDATE memory_items SET metadata_json = '{}'::jsonb WHERE metadata_json IS NULL")
    op.alter_column("memory_items", "metadata_json", nullable=False)


def downgrade() -> None:
    op.drop_column("memory_items", "metadata_json")
