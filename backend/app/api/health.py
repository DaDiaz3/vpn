from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse, summary="Service liveness")
async def health() -> HealthResponse:
    """Return process liveness only; dependency checks will be added separately."""
    return HealthResponse(status="ok")
