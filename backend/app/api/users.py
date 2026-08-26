from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.auth import AuthenticatedUser

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=AuthenticatedUser)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
