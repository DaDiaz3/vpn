from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.db.models import User, VPNServer
from app.db.session import get_db_session
from app.schemas.vpn import ProvisionRequest, ProvisionResponse
from app.services.vpn_provisioning import AccessDeniedError, CapacityExhaustedError, NodeUnavailableError, ProvisioningError, VPNProvisioningService
from uuid import UUID

router = APIRouter(prefix="/api/v1/vpn", tags=["vpn provisioning"])

@router.post("/provision", response_model=ProvisionResponse)
async def provision(payload: ProvisionRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> ProvisionResponse:
    try: credential = await VPNProvisioningService(session).provision(user, payload.server_id, payload.public_key)
    except AccessDeniedError: raise HTTPException(status_code=403, detail="VPN access is not active") from None
    except CapacityExhaustedError: raise HTTPException(status_code=409, detail="VPN server capacity exhausted") from None
    except NodeUnavailableError: raise HTTPException(status_code=503, detail="VPN node unavailable") from None
    except ProvisioningError as exc: raise HTTPException(status_code=400, detail=str(exc)) from None
    server = await session.get(VPNServer, credential.server_id)
    return ProvisionResponse(credential_id=credential.id, server={"id": server.id, "country": server.country, "city": server.city, "endpoint": server.endpoint, "public_key": server.wireguard_public_key}, client={"address": f"{credential.assigned_ip}/32"}, dns=[x.strip() for x in server.dns.split(",") if x.strip()], allowed_ips=["0.0.0.0/0", "::/0"])

@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(credential_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> None:
    try: await VPNProvisioningService(session).revoke(user, credential_id)
    except ProvisioningError: raise HTTPException(status_code=404, detail="Credential not found") from None
