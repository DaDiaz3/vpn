"""Add administrator identity, node credentials, and server freshness.

Revision ID: 20260826_02
Revises: 20260826_01
Create Date: 2026-08-26 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260826_02"
down_revision: str | Sequence[str] | None = "20260826_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("vpn_servers", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "node_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["vpn_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_id"),
    )
    op.drop_index("ix_server_metrics_server_id_timestamp", table_name="server_metrics")
    op.create_index("ix_server_metrics_latest", "server_metrics", ["server_id", "timestamp", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_server_metrics_latest", table_name="server_metrics")
    op.create_index(
        "ix_server_metrics_server_id_timestamp",
        "server_metrics",
        ["server_id", "timestamp"],
        unique=False,
    )
    op.drop_table("node_credentials")
    op.drop_column("vpn_servers", "last_seen_at")
    op.drop_column("users", "is_admin")
