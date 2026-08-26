import enum
import uuid
import sqlalchemy as sa
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class SubscriptionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REVOKED = "REVOKED"


class VPNServerStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class VPNCredentialStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        nullable=False,
    )
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    credentials: Mapped[list["VPNCredential"]] = relationship(back_populates="user")
    sessions: Mapped[list["VPNSession"]] = relationship(back_populates="user")
    connection_metrics: Mapped[list["ConnectionMetric"]] = relationship(back_populates="user")


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id", "user_id"),
        Index("ix_subscriptions_expires_at", "expires_at"),
        Index("ix_subscriptions_external_transaction_id", "external_transaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="subscriptions")


class VPNServer(TimestampMixin, Base):
    __tablename__ = "vpn_servers"
    __table_args__ = (CheckConstraint("capacity >= 0", name="ck_vpn_servers_capacity_nonnegative"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[VPNServerStatus] = mapped_column(
        Enum(VPNServerStatus, name="vpn_server_status"),
        default=VPNServerStatus.ONLINE,
        server_default=VPNServerStatus.ONLINE.value,
        nullable=False,
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    network_cidr: Mapped[str] = mapped_column(String(43), server_default="10.20.0.0/24", nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), server_default="", nullable=False)
    wireguard_public_key: Mapped[str] = mapped_column(String(64), server_default="", nullable=False)
    dns: Mapped[str] = mapped_column(String(255), server_default="1.1.1.1", nullable=False)

    credentials: Mapped[list["VPNCredential"]] = relationship(back_populates="server")
    sessions: Mapped[list["VPNSession"]] = relationship(back_populates="server")
    metrics: Mapped[list["ServerMetric"]] = relationship(back_populates="server")
    connection_metrics: Mapped[list["ConnectionMetric"]] = relationship(back_populates="server")
    node_credential: Mapped["NodeCredential | None"] = relationship(back_populates="server")


class NodeCredential(Base):
    """Per-node secret verifier; plaintext node secrets are never persisted."""

    __tablename__ = "node_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vpn_servers.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    server: Mapped[VPNServer] = relationship(back_populates="node_credential")


class VPNCredential(Base):
    __tablename__ = "vpn_credentials"
    __table_args__ = (
        Index("ix_vpn_credentials_user_id", "user_id"),
        Index("ix_vpn_credentials_server_id", "server_id"),
        Index("uq_vpn_credentials_server_assigned_ip", "server_id", "assigned_ip", unique=True, postgresql_where=sa.text("status = 'ACTIVE' AND assigned_ip IS NOT NULL")),
        Index("uq_vpn_credentials_active_identity", "user_id", "server_id", "public_key", unique=True, postgresql_where=sa.text("status = 'ACTIVE'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vpn_servers.id", ondelete="RESTRICT"), nullable=False
    )
    public_key: Mapped[str] = mapped_column(String(512), nullable=False)
    assigned_ip: Mapped[str | None] = mapped_column(String(43), nullable=True)
    node_sync_pending: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    status: Mapped[VPNCredentialStatus] = mapped_column(
        Enum(VPNCredentialStatus, name="vpn_credential_status"),
        default=VPNCredentialStatus.ACTIVE,
        server_default=VPNCredentialStatus.ACTIVE.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="credentials")
    server: Mapped[VPNServer] = relationship(back_populates="credentials")


class VPNSession(Base):
    __tablename__ = "vpn_sessions"
    __table_args__ = (
        CheckConstraint("bytes_in >= 0", name="ck_vpn_sessions_bytes_in_nonnegative"),
        CheckConstraint("bytes_out >= 0", name="ck_vpn_sessions_bytes_out_nonnegative"),
        Index("ix_vpn_sessions_user_id", "user_id"),
        Index("ix_vpn_sessions_server_id", "server_id"),
        Index("ix_vpn_sessions_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vpn_servers.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bytes_in: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    bytes_out: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    disconnect_reason: Mapped[str | None] = mapped_column(String(100))

    user: Mapped[User] = relationship(back_populates="sessions")
    server: Mapped[VPNServer] = relationship(back_populates="sessions")


class ServerMetric(Base):
    __tablename__ = "server_metrics"
    __table_args__ = (
        CheckConstraint("cpu_percent >= 0 AND cpu_percent <= 100", name="ck_server_metrics_cpu_percent"),
        CheckConstraint(
            "memory_percent >= 0 AND memory_percent <= 100",
            name="ck_server_metrics_memory_percent",
        ),
        CheckConstraint("bandwidth_in >= 0", name="ck_server_metrics_bandwidth_in_nonnegative"),
        CheckConstraint("bandwidth_out >= 0", name="ck_server_metrics_bandwidth_out_nonnegative"),
        CheckConstraint("active_users >= 0", name="ck_server_metrics_active_users_nonnegative"),
        CheckConstraint(
            "packet_loss_percent >= 0 AND packet_loss_percent <= 100",
            name="ck_server_metrics_packet_loss_percent",
        ),
        CheckConstraint("latency_ms >= 0", name="ck_server_metrics_latency_ms_nonnegative"),
        Index("ix_server_metrics_latest", "server_id", "timestamp", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vpn_servers.id", ondelete="RESTRICT"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cpu_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    memory_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    bandwidth_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bandwidth_out: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active_users: Mapped[int] = mapped_column(Integer, nullable=False)
    packet_loss_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    server: Mapped[VPNServer] = relationship(back_populates="metrics")


class ConnectionMetric(Base):
    __tablename__ = "connection_metrics"
    __table_args__ = (
        CheckConstraint("latency_ms >= 0", name="ck_connection_metrics_latency_ms_nonnegative"),
        CheckConstraint("download_mbps >= 0", name="ck_connection_metrics_download_mbps_nonnegative"),
        CheckConstraint("upload_mbps >= 0", name="ck_connection_metrics_upload_mbps_nonnegative"),
        Index("ix_connection_metrics_user_id_timestamp", "user_id", "timestamp"),
        Index("ix_connection_metrics_server_id_timestamp", "server_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vpn_servers.id", ondelete="RESTRICT"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    download_mbps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    upload_mbps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    connection_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disconnect_reason: Mapped[str | None] = mapped_column(String(100))

    user: Mapped[User] = relationship(back_populates="connection_metrics")
    server: Mapped[VPNServer] = relationship(back_populates="connection_metrics")
