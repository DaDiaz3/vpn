import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user
from app.core.config import get_auth_settings
from app.core.security import JWTService, hash_password
from app.db.base import Base
from app.db.models import User, UserStatus
from app.db.session import get_db_session
from app.main import create_app
from app.services.trials import AccessState, TrialService

LOCAL_TEST_DATABASE_URL = "postgresql+asyncpg://vpn_mvp:change-me-for-local-development@127.0.0.1:5432/vpn_mvp"
Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]
TEST_JWT_SECRET = "test-only-secret-not-for-production-0123456789"


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
    previous_secret = os.environ.get("JWT_SECRET_KEY")
    previous_expiry = os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    os.environ["JWT_SECRET_KEY"] = TEST_JWT_SECRET
    os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
    get_auth_settings.cache_clear()

    try:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await scenario(session_factory)
    finally:
        if previous_secret is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = previous_secret
        if previous_expiry is None:
            os.environ.pop("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", None)
        else:
            os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = previous_expiry
        get_auth_settings.cache_clear()
        await test_engine.dispose()
        async with control_engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        await control_engine.dispose()


@asynccontextmanager
async def api_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def register(client: httpx.AsyncClient, email: str = "user@example.com") -> httpx.Response:
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )


async def create_suspended_user(session_factory: async_sessionmaker[AsyncSession]) -> User:
    async with session_factory.begin() as session:
        user = User(
            email="suspended@example.com",
            password_hash=hash_password("secure-password"),
            status=UserStatus.SUSPENDED,
            trial_started_at=datetime.now(UTC),
            trial_ends_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(user)
        await session.flush()
        return user


def test_successful_registration() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await register(client, " User@Example.COM ")
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == "user@example.com"
        assert body["user"]["status"] == "ACTIVE"
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    run_database_test(scenario)


def test_duplicate_email_is_rejected() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            assert (await register(client)).status_code == 201
            response = await register(client, "USER@example.com")
        assert response.status_code == 409

    run_database_test(scenario)


def test_invalid_email_is_rejected() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "not-an-email", "password": "secure-password"},
            )
        assert response.status_code == 422

    run_database_test(scenario)


def test_short_password_is_rejected() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "user@example.com", "password": "short"},
            )
        assert response.status_code == 422

    run_database_test(scenario)


def test_password_is_hashed_and_not_exposed() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await register(client)
        assert response.status_code == 201
        assert "secure-password" not in response.text
        async with session_factory() as session:
            user = (await session.execute(select(User))).scalar_one()
        assert user.password_hash != "secure-password"
        assert user.password_hash.startswith("$argon2")

    run_database_test(scenario)


def test_successful_login() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            await register(client)
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "USER@example.com", "password": "secure-password"},
            )
        assert response.status_code == 200
        assert response.json()["access_token"]

    run_database_test(scenario)


def test_wrong_password_has_generic_error() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            await register(client)
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "wrong-password"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    run_database_test(scenario)


def test_unknown_email_has_same_generic_error() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "unknown@example.com", "password": "secure-password"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    run_database_test(scenario)


def test_access_token_contains_required_claims() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await register(client)
        body = response.json()
        payload = jwt.decode(body["access_token"], TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == body["user"]["id"]
        assert payload["typ"] == "access"
        assert payload["iat"] < payload["exp"]

    run_database_test(scenario)


def test_me_returns_user_for_valid_token() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            registration = await register(client)
            token = registration.json()["access_token"]
            response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == "user@example.com"
        assert "password_hash" not in response.json()

    run_database_test(scenario)


def test_me_requires_token() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    run_database_test(scenario)


def test_me_rejects_invalid_token() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer not-a-valid-token"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"

    run_database_test(scenario)


def test_registration_creates_seven_day_trial() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with api_client(session_factory) as client:
            response = await register(client)
        body = response.json()["user"]
        started_at = datetime.fromisoformat(body["trial_started_at"].replace("Z", "+00:00"))
        ends_at = datetime.fromisoformat(body["trial_ends_at"].replace("Z", "+00:00"))
        assert started_at.tzinfo is not None
        assert ends_at - started_at == timedelta(days=7)

    run_database_test(scenario)


def test_expired_trial_state() -> None:
    user = User(
        email="expired@example.com",
        password_hash="not-used",
        trial_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        trial_ends_at=datetime(2026, 1, 8, tzinfo=UTC),
    )
    state = TrialService().determine_access_state(user, now=datetime(2026, 1, 8, tzinfo=UTC))
    assert state is AccessState.TRIAL_EXPIRED


def test_suspended_user_cannot_authenticate_or_use_protected_endpoint() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        suspended_user = await create_suspended_user(session_factory)
        token = JWTService(get_auth_settings()).create_access_token(suspended_user.id)
        async with api_client(session_factory) as client:
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "suspended@example.com", "password": "secure-password"},
            )
            me_response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert login_response.status_code == 401
        assert login_response.json()["detail"] == "Invalid email or password"
        assert me_response.status_code == 401

    run_database_test(scenario)
