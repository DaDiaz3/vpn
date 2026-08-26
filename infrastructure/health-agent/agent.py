"""Minimal HTTPS health reporter for a VPN node; it does not inspect VPN traffic."""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse

import httpx
import psutil


def log_event(event: str, **fields: object) -> None:
    logging.getLogger("health_agent").info(json.dumps({"event": event, **fields}, default=str))


@dataclass(frozen=True)
class AgentSettings:
    control_plane_url: str
    server_id: uuid.UUID
    node_secret: str
    heartbeat_interval_seconds: int
    active_users: int
    latency_ms: Decimal
    packet_loss_percent: Decimal

    @classmethod
    def from_environment(cls) -> "AgentSettings":
        url = os.environ["CONTROL_PLANE_URL"].rstrip("/")
        if urlparse(url).scheme != "https" and os.getenv("ALLOW_INSECURE_HTTP") != "true":
            raise RuntimeError("CONTROL_PLANE_URL must use HTTPS (set ALLOW_INSECURE_HTTP=true only for local development).")
        interval = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
        if interval <= 0:
            raise RuntimeError("HEARTBEAT_INTERVAL_SECONDS must be positive.")
        secret = os.environ["NODE_SECRET"]
        if not secret:
            raise RuntimeError("NODE_SECRET must be set.")
        return cls(
            control_plane_url=url,
            server_id=uuid.UUID(os.environ["NODE_SERVER_ID"]),
            node_secret=secret,
            heartbeat_interval_seconds=interval,
            active_users=int(os.getenv("ACTIVE_USERS", "0")),
            latency_ms=Decimal(os.getenv("HEALTH_AGENT_LATENCY_MS", "0")),
            packet_loss_percent=Decimal(os.getenv("HEALTH_AGENT_PACKET_LOSS_PERCENT", "0")),
        )


class MetricCollector:
    def __init__(self) -> None:
        self._previous_network = psutil.net_io_counters()
        self._previous_time = time.monotonic()

    def collect(self, settings: AgentSettings) -> dict[str, object]:
        current_network = psutil.net_io_counters()
        current_time = time.monotonic()
        elapsed = max(current_time - self._previous_time, 0.001)
        bandwidth_in = int((current_network.bytes_recv - self._previous_network.bytes_recv) / elapsed)
        bandwidth_out = int((current_network.bytes_sent - self._previous_network.bytes_sent) / elapsed)
        self._previous_network, self._previous_time = current_network, current_time
        return {
            "server_id": str(settings.server_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "bandwidth_in": max(bandwidth_in, 0),
            "bandwidth_out": max(bandwidth_out, 0),
            "active_users": settings.active_users,
            "packet_loss_percent": str(settings.packet_loss_percent),
            "latency_ms": str(settings.latency_ms),
        }


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
    settings = AgentSettings.from_environment()
    collector = MetricCollector()
    endpoint = f"{settings.control_plane_url}/api/v1/node/heartbeat"
    with httpx.Client(timeout=10.0) as client:
        while True:
            try:
                response = client.post(
                    endpoint,
                    json=collector.collect(settings),
                    headers={"X-Node-Secret": settings.node_secret},
                )
                response.raise_for_status()
                log_event("heartbeat_sent", server_id=settings.server_id, status=response.json().get("status"))
            except httpx.RequestError as error:
                log_event("heartbeat_network_error", server_id=settings.server_id, error_type=type(error).__name__)
            except httpx.HTTPStatusError as error:
                log_event("heartbeat_rejected", server_id=settings.server_id, status_code=error.response.status_code)
            time.sleep(settings.heartbeat_interval_seconds)


if __name__ == "__main__":
    main()
