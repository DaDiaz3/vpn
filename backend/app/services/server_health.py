import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import HealthSettings
from app.core.logging import log_event
from app.db.models import ServerMetric, VPNServer, VPNServerStatus
from app.repositories.servers import ServerRepository
from app.schemas.servers import NodeHeartbeatRequest

logger = logging.getLogger("vpn_mvp.server_health")


class InvalidHeartbeatTimestampError(Exception):
    pass


class ServerHealthService:
    def __init__(self, session: AsyncSession, settings: HealthSettings) -> None:
        self._session = session
        self._settings = settings
        self._servers = ServerRepository(session)

    async def process_heartbeat(self, server: VPNServer, heartbeat: NodeHeartbeatRequest) -> VPNServerStatus:
        now = datetime.now(UTC)
        if abs((now - heartbeat.timestamp.astimezone(UTC)).total_seconds()) > self._settings.max_timestamp_skew_seconds:
            raise InvalidHeartbeatTimestampError

        metric = ServerMetric(
            server_id=server.id,
            timestamp=heartbeat.timestamp.astimezone(UTC),
            cpu_percent=heartbeat.cpu_percent,
            memory_percent=heartbeat.memory_percent,
            bandwidth_in=heartbeat.bandwidth_in,
            bandwidth_out=heartbeat.bandwidth_out,
            active_users=heartbeat.active_users,
            packet_loss_percent=heartbeat.packet_loss_percent,
            latency_ms=heartbeat.latency_ms,
        )
        self._session.add(metric)
        server.last_seen_at = now
        previous_status = server.status
        if server.status is not VPNServerStatus.MAINTENANCE:
            server.status = self.status_for_metric(server, metric)
        if server.status is not previous_status:
            log_event(logger, "server_health_state_changed", server_id=server.id, status=server.status.value)
        log_event(logger, "heartbeat_received", server_id=server.id, status=server.status.value)
        return server.status

    def status_for_metric(self, server: VPNServer, metric: ServerMetric) -> VPNServerStatus:
        load_percent = (Decimal(metric.active_users) / Decimal(server.capacity)) * 100
        is_degraded = (
            metric.cpu_percent >= self._settings.cpu_degraded_threshold
            or metric.memory_percent >= self._settings.memory_degraded_threshold
            or metric.packet_loss_percent >= self._settings.packet_loss_degraded_threshold
            or metric.latency_ms >= self._settings.latency_degraded_threshold_ms
            or load_percent >= self._settings.load_degraded_threshold
        )
        return VPNServerStatus.DEGRADED if is_degraded else VPNServerStatus.ONLINE

    async def mark_stale_servers_offline(self, now: datetime | None = None) -> int:
        current_time = now or datetime.now(UTC)
        stale_before = current_time - timedelta(seconds=self._settings.offline_after_seconds)
        result = await self._session.execute(
            update(VPNServer)
            .where(
                VPNServer.status != VPNServerStatus.MAINTENANCE,
                (VPNServer.last_seen_at.is_(None)) | (VPNServer.last_seen_at < stale_before),
            )
            .values(status=VPNServerStatus.OFFLINE)
        )
        changed = result.rowcount or 0
        if changed:
            log_event(logger, "server_health_state_changed", status=VPNServerStatus.OFFLINE.value, count=changed)
        return changed

    async def latest_metrics(self) -> list[tuple[VPNServer, ServerMetric | None]]:
        await self.mark_stale_servers_offline()
        return await self._servers.list_available_with_latest_metric()
