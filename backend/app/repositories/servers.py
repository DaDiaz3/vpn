import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NodeCredential, ServerMetric, VPNServer, VPNServerStatus


class ServerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, server_id: uuid.UUID) -> VPNServer | None:
        return await self._session.get(VPNServer, server_id)

    async def get_node_credential(self, server_id: uuid.UUID) -> NodeCredential | None:
        result = await self._session.execute(
            select(NodeCredential).where(NodeCredential.server_id == server_id, NodeCredential.revoked_at.is_(None))
        )
        return result.scalar_one_or_none()

    def add(self, server: VPNServer) -> None:
        self._session.add(server)

    def add_node_credential(self, credential: NodeCredential) -> None:
        self._session.add(credential)

    async def list_all(self) -> list[VPNServer]:
        result = await self._session.execute(select(VPNServer).order_by(VPNServer.country, VPNServer.city, VPNServer.name))
        return list(result.scalars())

    async def list_available_with_latest_metric(self) -> list[tuple[VPNServer, ServerMetric | None]]:
        latest_metric_id = (
            select(ServerMetric.id)
            .where(ServerMetric.server_id == VPNServer.id)
            .order_by(ServerMetric.timestamp.desc(), ServerMetric.id.desc())
            .limit(1)
            .correlate(VPNServer)
            .scalar_subquery()
        )
        statement: Select[tuple[VPNServer, ServerMetric | None]] = (
            select(VPNServer, ServerMetric)
            .outerjoin(ServerMetric, ServerMetric.id == latest_metric_id)
            .where(VPNServer.status.in_([VPNServerStatus.ONLINE, VPNServerStatus.DEGRADED]))
            .order_by(VPNServer.country, VPNServer.city, VPNServer.name)
        )
        result = await self._session.execute(statement)
        return list(result.all())
