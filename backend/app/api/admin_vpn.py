from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_admin
from app.db.models import User
from app.db.session import get_db_session
from app.services.vpn_provisioning import VPNProvisioningService
router = APIRouter(prefix="/api/v1/admin/vpn", tags=["admin vpn"])
@router.post("/reconcile")
async def reconcile(_: User = Depends(get_current_admin), session: AsyncSession = Depends(get_db_session)) -> dict[str, int]:
    return {"reconciled": await VPNProvisioningService(session).reconcile_pending()}
