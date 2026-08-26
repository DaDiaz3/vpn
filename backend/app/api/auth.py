from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_auth_settings
from app.db.session import get_db_session
from app.schemas.auth import AccessTokenResponse, CredentialsRequest
from app.services.auth import AuthService, EmailAlreadyRegisteredError, InactiveUserError, InvalidCredentialsError

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/register", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    credentials: CredentialsRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AccessTokenResponse:
    try:
        user, token = await AuthService(session, get_auth_settings()).register(
            email=str(credentials.email),
            password=credentials.password.get_secret_value(),
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None
    return AccessTokenResponse(access_token=token, user=user)


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    credentials: CredentialsRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AccessTokenResponse:
    try:
        user, token = await AuthService(session, get_auth_settings()).login(
            email=str(credentials.email),
            password=credentials.password.get_secret_value(),
        )
    except (InvalidCredentialsError, InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from None
    return AccessTokenResponse(access_token=token, user=user)
