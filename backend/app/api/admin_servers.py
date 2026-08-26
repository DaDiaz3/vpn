import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin
from app.core.security import hash_password
from app.db.models import NodeCredential, User, VPNServer, VPNServerStatus
from app.db.session import get_db_session
from app.repositories.servers import ServerRepository
from app.schemas.servers import AdminServerCreate, AdminServerResponse, AdminServerUpdate

router = APIRouter(prefix="/api/v1/admin/servers", tags=["admin servers"])


@router.post("", response_model=AdminServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: AdminServerCreate,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
) -> VPNServer:
    server = VPNServer(
        name=payload.name,
        country=payload.country,
        city=payload.city,
        hostname=payload.hostname,
        capacity=payload.capacity,
        status=VPNServerStatus.OFFLINE,
        network_cidr=payload.network_cidr,
        endpoint=payload.endpoint,
        wireguard_public_key=payload.wireguard_public_key,
        dns=payload.dns,
    )
    repository = ServerRepository(session)
    repository.add(server)
    await session.flush()
    repository.add_node_credential(
        NodeCredential(server_id=server.id, secret_hash=hash_password(payload.node_secret.get_secret_value()))
    )
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Server hostname already exists") from None
    return server


@router.get("", response_model=list[AdminServerResponse])
async def list_admin_servers(
    _: User = Depends(get_current_admin), session: AsyncSession = Depends(get_db_session)
) -> list[VPNServer]:
    return await ServerRepository(session).list_all()


@router.patch("/{server_id}", response_model=AdminServerResponse)
async def update_server(
    server_id: uuid.UUID,
    payload: AdminServerUpdate,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
) -> VPNServer:
    server = await ServerRepository(session).get_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, field, value)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Server hostname already exists") from None
    await session.refresh(server)
    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: uuid.UUID,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    server = await ServerRepository(session).get_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    await session.delete(server)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
