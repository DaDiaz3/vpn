import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_auth_settings, get_health_settings
from app.core.security import JWTService, hash_password
from app.db.models import NodeCredential, ServerMetric, User, UserStatus, VPNServer, VPNServerStatus
from app.repositories.servers import ServerRepository
from app.services.server_health import ServerHealthService
from tests.test_auth import api_client, run_database_test

NODE_SECRET = "node-secret-for-tests-0123456789-abcdef"


def heartbeat_payload(server_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "server_id": server_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "cpu_percent": 20.0,
        "memory_percent": 30.0,
        "bandwidth_in": 100,
        "bandwidth_out": 200,
        "active_users": 10,
        "packet_loss_percent": 0.1,
        "latency_ms": 20,
    }
    payload.update(overrides)
    return payload


async def create_user(session_factory: async_sessionmaker[AsyncSession], *, admin: bool = False) -> tuple[User, str]:
    async with session_factory.begin() as session:
        user = User(
            email="admin@example.com" if admin else "user@example.com",
            password_hash=hash_password("secure-password"),
            status=UserStatus.ACTIVE,
            is_admin=admin,
            trial_started_at=datetime.now(UTC),
            trial_ends_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(user)
        await session.flush()
        return user, JWTService(get_auth_settings()).create_access_token(user.id)


async def create_server(
    session_factory: async_sessionmaker[AsyncSession], *, secret: str = NODE_SECRET, hostname: str = "jp-tyo-1.example.invalid"
) -> VPNServer:
    async with session_factory.begin() as session:
        server = VPNServer(
            name="Japan 01",
            country="JP",
            city="Tokyo",
            hostname=hostname,
            capacity=100,
            status=VPNServerStatus.OFFLINE,
        )
        session.add(server)
        await session.flush()
        session.add(NodeCredential(server_id=server.id, secret_hash=hash_password(secret)))
        return server


def test_admin_can_create_server_without_exposing_secret() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        _, token = await create_user(factory, admin=True)
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/admin/servers",
                headers={"Authorization": f"Bearer {token}"},
                json={"name": "Japan 01", "country": "jp", "city": "Tokyo", "hostname": "jp-tyo-1.example.invalid", "capacity": 100, "node_secret": NODE_SECRET},
            )
        assert response.status_code == 201
        assert "node_secret" not in response.json()
        assert "secret_hash" not in response.json()
        async with factory() as session:
            assert (await session.execute(select(NodeCredential))).scalar_one().secret_hash != NODE_SECRET

    run_database_test(scenario)


def test_non_admin_cannot_create_server() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        _, token = await create_user(factory)
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/admin/servers",
                headers={"Authorization": f"Bearer {token}"},
                json={"name": "Japan 01", "country": "JP", "city": "Tokyo", "hostname": "jp-tyo-1.example.invalid", "capacity": 100, "node_secret": NODE_SECRET},
            )
        assert response.status_code == 403

    run_database_test(scenario)


def test_admin_can_update_server() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        _, token = await create_user(factory, admin=True)
        server = await create_server(factory)
        async with api_client(factory) as client:
            response = await client.patch(
                f"/api/v1/admin/servers/{server.id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"capacity": 200, "city": "Osaka"},
            )
        assert response.status_code == 200
        assert response.json()["capacity"] == 200
        assert response.json()["city"] == "Osaka"

    run_database_test(scenario)


def test_node_can_authenticate_and_heartbeat_updates_metrics() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        server = await create_server(factory)
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/node/heartbeat",
                headers={"X-Node-Secret": NODE_SECRET},
                json=heartbeat_payload(str(server.id)),
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ONLINE"
        async with factory() as session:
            metric = (await session.execute(select(ServerMetric))).scalar_one()
            updated_server = await session.get(VPNServer, server.id)
        assert metric.server_id == server.id
        assert updated_server.last_seen_at is not None

    run_database_test(scenario)


def test_invalid_node_credential_is_rejected_and_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        server = await create_server(factory)
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/node/heartbeat",
                headers={"X-Node-Secret": "wrong-node-secret"},
                json=heartbeat_payload(str(server.id)),
            )
        assert response.status_code == 401

    caplog.set_level(logging.INFO, logger="vpn_mvp.node")
    run_database_test(scenario)
    assert NODE_SECRET not in caplog.text
    assert "wrong-node-secret" not in caplog.text


def test_node_cannot_send_heartbeat_for_another_server() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        await create_server(factory)
        other = await create_server(
            factory,
            secret="another-node-secret-0123456789-abcdef",
            hostname="jp-tyo-2.example.invalid",
        )
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/node/heartbeat",
                headers={"X-Node-Secret": NODE_SECRET},
                json=heartbeat_payload(str(other.id)),
            )
        assert response.status_code == 401

    run_database_test(scenario)


@pytest.mark.parametrize(
    ("field", "value"),
    [("cpu_percent", 101), ("memory_percent", 101), ("packet_loss_percent", 101), ("latency_ms", -1), ("active_users", -1)],
)
def test_invalid_heartbeat_metric_is_rejected(field: str, value: int) -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        server = await create_server(factory)
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/node/heartbeat",
                headers={"X-Node-Secret": NODE_SECRET},
                json=heartbeat_payload(str(server.id), **{field: value}),
            )
        assert response.status_code == 422

    run_database_test(scenario)


def test_bad_metrics_mark_server_degraded() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        server = await create_server(factory)
        async with api_client(factory) as client:
            response = await client.post(
                "/api/v1/node/heartbeat",
                headers={"X-Node-Secret": NODE_SECRET},
                json=heartbeat_payload(str(server.id), cpu_percent=90),
            )
        assert response.json()["status"] == "DEGRADED"

    run_database_test(scenario)


def test_stale_heartbeat_marks_server_offline() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        server = await create_server(factory)
        async with factory.begin() as session:
            stored = await session.get(VPNServer, server.id)
            stored.last_seen_at = datetime.now(UTC) - timedelta(seconds=1000)
            stored.status = VPNServerStatus.ONLINE
        async with factory.begin() as session:
            changed = await ServerHealthService(session, get_health_settings()).mark_stale_servers_offline()
            assert changed == 1
        async with factory() as session:
            assert (await session.get(VPNServer, server.id)).status is VPNServerStatus.OFFLINE

    run_database_test(scenario)


def test_user_sees_public_latest_server_metrics_without_n_plus_one() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession]) -> None:
        _, token = await create_user(factory)
        server = await create_server(factory)
        async with api_client(factory) as client:
            await client.post("/api/v1/node/heartbeat", headers={"X-Node-Secret": NODE_SECRET}, json=heartbeat_payload(str(server.id), latency_ms=82, active_users=34))
            await client.post("/api/v1/node/heartbeat", headers={"X-Node-Secret": NODE_SECRET}, json=heartbeat_payload(str(server.id), latency_ms=40, active_users=21))
            response = await client.get("/api/v1/servers", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        public_server = response.json()["servers"][0]
        assert public_server["latency_ms"] == 40
        assert public_server["active_users"] == 21
        assert "hostname" not in public_server
        assert "secret" not in str(public_server).lower()

        statements: list[str] = []
        engine = factory.kw["bind"].sync_engine
        def observe(*args: object) -> None:
            statements.append(str(args[2]))
        event.listen(engine, "before_cursor_execute", observe)
        try:
            async with factory() as session:
                records = await ServerRepository(session).list_available_with_latest_metric()
            assert len(records) == 1
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        assert len(statements) == 1

    run_database_test(scenario)
