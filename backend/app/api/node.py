import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_health_settings
from app.core.logging import log_event
from app.core.security import verify_password
from app.db.session import get_db_session
from app.repositories.servers import ServerRepository
from app.schemas.servers import HeartbeatResponse, NodeHeartbeatRequest
from app.services.server_health import InvalidHeartbeatTimestampError, ServerHealthService

logger = logging.getLogger("vpn_mvp.node")
router = APIRouter(prefix="/api/v1/node", tags=["node health"])


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    payload: NodeHeartbeatRequest,
    x_node_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> HeartbeatResponse:
    repository = ServerRepository(session)
    server = await repository.get_by_id(payload.server_id)
    credential = await repository.get_node_credential(payload.server_id) if server else None
    if credential is None or x_node_secret is None or not verify_password(x_node_secret, credential.secret_hash):
        log_event(logger, "heartbeat_rejected", server_id=payload.server_id, reason="authentication_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid node credentials")
    try:
        server_status = await ServerHealthService(session, get_health_settings()).process_heartbeat(server, payload)
    except InvalidHeartbeatTimestampError:
        log_event(logger, "heartbeat_rejected", server_id=payload.server_id, reason="timestamp_out_of_range")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid heartbeat timestamp") from None
    return HeartbeatResponse(status=server_status)
