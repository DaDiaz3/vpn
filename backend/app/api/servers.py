from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_health_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.servers import ServerListResponse, ServerPublic
from app.services.server_health import ServerHealthService

router = APIRouter(prefix="/api/v1/servers", tags=["servers"])


@router.get("", response_model=ServerListResponse)
async def list_servers(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ServerListResponse:
    records = await ServerHealthService(session, get_health_settings()).latest_metrics()
    servers: list[ServerPublic] = []
    for server, metric in records:
        load_percent = None
        if metric is not None:
            load_percent = (Decimal(metric.active_users) / Decimal(server.capacity)) * 100
        servers.append(
            ServerPublic(
                id=server.id,
                name=server.name,
                country=server.country,
                city=server.city,
                status=server.status,
                latency_ms=metric.latency_ms if metric else None,
                load_percent=load_percent,
                active_users=metric.active_users if metric else None,
            )
        )
    return ServerListResponse(servers=servers)
