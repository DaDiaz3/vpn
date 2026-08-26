import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    ConnectionMetric,
    ServerMetric,
    Subscription,
    SubscriptionStatus,
    User,
    UserStatus,
    VPNCredential,
    VPNCredentialStatus,
    VPNServer,
    VPNServerStatus,
    VPNSession,
)

LOCAL_TEST_DATABASE_URL = "postgresql+asyncpg://vpn_mvp:change-me-for-local-development@127.0.0.1:5432/vpn_mvp"
Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]


def run_database_test(scenario: Scenario) -> None:
    asyncio.run(_run_database_test(scenario))


async def _run_database_test(scenario: Scenario) -> None:
    database_url = os.getenv("TEST_DATABASE_URL", LOCAL_TEST_DATABASE_URL)
    schema_name = f"test_{uuid.uuid4().hex}"
    control_engine = create_async_engine(database_url)

    async with control_engine.begin() as connection:
        await connection.execute(text(f"CREATE SCHEMA {schema_name}"))

    test_engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    try:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await scenario(session_factory)
    finally:
        await test_engine.dispose()
        async with control_engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        await control_engine.dispose()


def now() -> datetime:
    return datetime.now(UTC)


async def create_user(session: AsyncSession, email: str = "user@example.com") -> User:
    user = User(email=email, password_hash="argon2id-placeholder-hash")
    session.add(user)
    await session.flush()
    return user


async def create_server(session: AsyncSession) -> VPNServer:
    server = VPNServer(
        name="Almaty 1",
        country="KZ",
        city="Almaty",
        hostname="kz-ala-1.example.invalid",
        status=VPNServerStatus.ONLINE,
        capacity=1_000,
    )
    session.add(server)
    await session.flush()
    return server


def test_create_user() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            user = await create_user(session)
            assert isinstance(user.id, uuid.UUID)
            assert user.status is UserStatus.ACTIVE
            assert user.created_at is not None

    run_database_test(scenario)


def test_user_email_is_unique() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            await create_user(session)
            await session.commit()
            session.add(User(email="user@example.com", password_hash="another-hash"))
            with pytest.raises(IntegrityError):
                await session.commit()

    run_database_test(scenario)


def test_create_subscription() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            user = await create_user(session)
            subscription = Subscription(
                user_id=user.id,
                provider="app_store",
                external_transaction_id="2000000123456789",
                status=SubscriptionStatus.ACTIVE,
                product_id="com.example.vpn.monthly",
                started_at=now(),
                expires_at=now() + timedelta(days=30),
            )
            session.add(subscription)
            await session.flush()
            assert subscription.user_id == user.id
            assert subscription.user is user

    run_database_test(scenario)


def test_create_vpn_server() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            server = await create_server(session)
            assert isinstance(server.id, uuid.UUID)
            assert server.status is VPNServerStatus.ONLINE

    run_database_test(scenario)


def test_create_vpn_credential() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            user = await create_user(session)
            server = await create_server(session)
            credential = VPNCredential(
                user_id=user.id,
                server_id=server.id,
                public_key="public-key-only",
            )
            session.add(credential)
            await session.flush()
            assert credential.status is VPNCredentialStatus.ACTIVE
            assert credential.user is user
            assert credential.server is server

    run_database_test(scenario)


def test_foreign_key_relationships_are_enforced() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            session.add(
                VPNCredential(
                    user_id=uuid.uuid4(),
                    server_id=uuid.uuid4(),
                    public_key="public-key-only",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()

    run_database_test(scenario)


def test_create_vpn_session() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            user = await create_user(session)
            server = await create_server(session)
            vpn_session = VPNSession(
                user_id=user.id,
                server_id=server.id,
                started_at=now(),
                bytes_in=512,
                bytes_out=256,
                disconnect_reason="user_requested",
            )
            session.add(vpn_session)
            await session.flush()
            assert vpn_session.user is user
            assert vpn_session.server is server

    run_database_test(scenario)


def test_create_server_metric() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            server = await create_server(session)
            metric = ServerMetric(
                server_id=server.id,
                timestamp=now(),
                cpu_percent=Decimal("25.50"),
                memory_percent=Decimal("40.00"),
                bandwidth_in=1000,
                bandwidth_out=2000,
                active_users=10,
                packet_loss_percent=Decimal("0.10"),
                latency_ms=Decimal("42.00"),
            )
            session.add(metric)
            await session.flush()
            assert metric.server is server

    run_database_test(scenario)


def test_create_connection_metric() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory.begin() as session:
            user = await create_user(session)
            server = await create_server(session)
            metric = ConnectionMetric(
                user_id=user.id,
                server_id=server.id,
                timestamp=now(),
                latency_ms=Decimal("42.00"),
                download_mbps=Decimal("100.00"),
                upload_mbps=Decimal("50.00"),
                connection_success=True,
            )
            session.add(metric)
            await session.flush()
            assert metric.user is user
            assert metric.server is server

    run_database_test(scenario)
