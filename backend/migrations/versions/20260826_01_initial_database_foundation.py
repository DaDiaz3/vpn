"""Initial database foundation.

Revision ID: 20260826_01
Revises:
Create Date: 2026-08-26 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260826_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_status = postgresql.ENUM("ACTIVE", "SUSPENDED", "DELETED", name="user_status", create_type=False)
subscription_status = postgresql.ENUM(
    "PENDING", "ACTIVE", "EXPIRED", "CANCELLED", "REVOKED", name="subscription_status", create_type=False
)
vpn_server_status = postgresql.ENUM(
    "ONLINE", "DEGRADED", "OFFLINE", "MAINTENANCE", name="vpn_server_status", create_type=False
)
vpn_credential_status = postgresql.ENUM("ACTIVE", "REVOKED", name="vpn_credential_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    user_status.create(bind, checkfirst=False)
    subscription_status.create(bind, checkfirst=False)
    vpn_server_status.create(bind, checkfirst=False)
    vpn_credential_status.create(bind, checkfirst=False)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("status", user_status, server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "vpn_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("status", vpn_server_status, server_default="ONLINE", nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("capacity >= 0", name="ck_vpn_servers_capacity_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_transaction_id", sa.String(length=255), nullable=False),
        sa.Column("status", subscription_status, nullable=False),
        sa.Column("product_id", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False)
    op.create_index("ix_subscriptions_expires_at", "subscriptions", ["expires_at"], unique=False)
    op.create_index(
        "ix_subscriptions_external_transaction_id",
        "subscriptions",
        ["external_transaction_id"],
        unique=False,
    )

    op.create_table(
        "vpn_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_key", sa.String(length=512), nullable=False),
        sa.Column("status", vpn_credential_status, server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["vpn_servers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vpn_credentials_user_id", "vpn_credentials", ["user_id"], unique=False)
    op.create_index("ix_vpn_credentials_server_id", "vpn_credentials", ["server_id"], unique=False)

    op.create_table(
        "vpn_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bytes_in", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("bytes_out", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("disconnect_reason", sa.String(length=100), nullable=True),
        sa.CheckConstraint("bytes_in >= 0", name="ck_vpn_sessions_bytes_in_nonnegative"),
        sa.CheckConstraint("bytes_out >= 0", name="ck_vpn_sessions_bytes_out_nonnegative"),
        sa.ForeignKeyConstraint(["server_id"], ["vpn_servers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vpn_sessions_user_id", "vpn_sessions", ["user_id"], unique=False)
    op.create_index("ix_vpn_sessions_server_id", "vpn_sessions", ["server_id"], unique=False)
    op.create_index("ix_vpn_sessions_started_at", "vpn_sessions", ["started_at"], unique=False)

    op.create_table(
        "server_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("memory_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("bandwidth_in", sa.BigInteger(), nullable=False),
        sa.Column("bandwidth_out", sa.BigInteger(), nullable=False),
        sa.Column("active_users", sa.Integer(), nullable=False),
        sa.Column("packet_loss_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("latency_ms", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.CheckConstraint("active_users >= 0", name="ck_server_metrics_active_users_nonnegative"),
        sa.CheckConstraint("bandwidth_in >= 0", name="ck_server_metrics_bandwidth_in_nonnegative"),
        sa.CheckConstraint("bandwidth_out >= 0", name="ck_server_metrics_bandwidth_out_nonnegative"),
        sa.CheckConstraint("cpu_percent >= 0 AND cpu_percent <= 100", name="ck_server_metrics_cpu_percent"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_server_metrics_latency_ms_nonnegative"),
        sa.CheckConstraint("memory_percent >= 0 AND memory_percent <= 100", name="ck_server_metrics_memory_percent"),
        sa.CheckConstraint("packet_loss_percent >= 0 AND packet_loss_percent <= 100", name="ck_server_metrics_packet_loss_percent"),
        sa.ForeignKeyConstraint(["server_id"], ["vpn_servers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_server_metrics_server_id_timestamp", "server_metrics", ["server_id", "timestamp"], unique=False)

    op.create_table(
        "connection_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("download_mbps", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("upload_mbps", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("connection_success", sa.Boolean(), nullable=False),
        sa.Column("disconnect_reason", sa.String(length=100), nullable=True),
        sa.CheckConstraint("download_mbps >= 0", name="ck_connection_metrics_download_mbps_nonnegative"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_connection_metrics_latency_ms_nonnegative"),
        sa.CheckConstraint("upload_mbps >= 0", name="ck_connection_metrics_upload_mbps_nonnegative"),
        sa.ForeignKeyConstraint(["server_id"], ["vpn_servers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_connection_metrics_user_id_timestamp", "connection_metrics", ["user_id", "timestamp"], unique=False
    )
    op.create_index(
        "ix_connection_metrics_server_id_timestamp", "connection_metrics", ["server_id", "timestamp"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_connection_metrics_server_id_timestamp", table_name="connection_metrics")
    op.drop_index("ix_connection_metrics_user_id_timestamp", table_name="connection_metrics")
    op.drop_table("connection_metrics")
    op.drop_index("ix_server_metrics_server_id_timestamp", table_name="server_metrics")
    op.drop_table("server_metrics")
    op.drop_index("ix_vpn_sessions_started_at", table_name="vpn_sessions")
    op.drop_index("ix_vpn_sessions_server_id", table_name="vpn_sessions")
    op.drop_index("ix_vpn_sessions_user_id", table_name="vpn_sessions")
    op.drop_table("vpn_sessions")
    op.drop_index("ix_vpn_credentials_server_id", table_name="vpn_credentials")
    op.drop_index("ix_vpn_credentials_user_id", table_name="vpn_credentials")
    op.drop_table("vpn_credentials")
    op.drop_index("ix_subscriptions_external_transaction_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_expires_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("vpn_servers")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    vpn_credential_status.drop(bind, checkfirst=False)
    vpn_server_status.drop(bind, checkfirst=False)
    subscription_status.drop(bind, checkfirst=False)
    user_status.drop(bind, checkfirst=False)
