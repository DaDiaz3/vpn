import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret_key: str
    access_token_expire_minutes: int


@dataclass(frozen=True)
class HealthSettings:
    heartbeat_interval_seconds: int
    offline_after_seconds: int
    max_timestamp_skew_seconds: int
    cpu_degraded_threshold: float
    memory_degraded_threshold: float
    packet_loss_degraded_threshold: float
    latency_degraded_threshold_ms: float
    load_degraded_threshold: float


@lru_cache
def get_auth_settings() -> AuthSettings:
    """Load authentication configuration without ever supplying a fallback secret."""
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be set.")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters long.")

    try:
        expiry_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    except ValueError as error:
        raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be an integer.") from error

    if expiry_minutes <= 0:
        raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be positive.")

    return AuthSettings(jwt_secret_key=secret, access_token_expire_minutes=expiry_minutes)


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error
    if value <= 0:
        raise RuntimeError(f"{name} must be positive.")
    return value


def _percentage(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be a number.") from error
    if not 0 <= value <= 100:
        raise RuntimeError(f"{name} must be between 0 and 100.")
    return value


@lru_cache
def get_health_settings() -> HealthSettings:
    heartbeat_interval = _positive_int("NODE_HEARTBEAT_INTERVAL_SECONDS", 30)
    offline_after = _positive_int("NODE_OFFLINE_AFTER_SECONDS", 90)
    if offline_after < heartbeat_interval:
        raise RuntimeError("NODE_OFFLINE_AFTER_SECONDS must be at least the heartbeat interval.")
    return HealthSettings(
        heartbeat_interval_seconds=heartbeat_interval,
        offline_after_seconds=offline_after,
        max_timestamp_skew_seconds=_positive_int("NODE_MAX_TIMESTAMP_SKEW_SECONDS", 300),
        cpu_degraded_threshold=_percentage("SERVER_CPU_DEGRADED_THRESHOLD", 85),
        memory_degraded_threshold=_percentage("SERVER_MEMORY_DEGRADED_THRESHOLD", 85),
        packet_loss_degraded_threshold=_percentage("SERVER_PACKET_LOSS_DEGRADED_THRESHOLD", 5),
        latency_degraded_threshold_ms=float(_positive_int("SERVER_LATENCY_DEGRADED_THRESHOLD_MS", 250)),
        load_degraded_threshold=_percentage("SERVER_LOAD_DEGRADED_THRESHOLD", 90),
    )
