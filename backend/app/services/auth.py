from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AuthSettings
from app.core.security import JWTService, hash_password, verify_password
from app.db.models import User, UserStatus
from app.repositories.users import UserRepository

# Valid Argon2id hash for a non-user value. It equalizes failed-login work when no user exists.
DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$Raquw30QwVucBDDOPPBEoQ$YOmFhdI5T9ai0Cici44CVEScewo+ynN4dSMZKizz1wI"


class EmailAlreadyRegisteredError(Exception):
    """Raised when registration conflicts with an existing email address."""


class InvalidCredentialsError(Exception):
    """Raised for all authentication failures exposed to clients."""


class InactiveUserError(Exception):
    """Raised when a non-active user attempts to use an authenticated operation."""


class AuthService:
    def __init__(self, session: AsyncSession, settings: AuthSettings) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._jwt = JWTService(settings)

    async def register(self, *, email: str, password: str) -> tuple[User, str]:
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError

        trial_started_at = datetime.now(UTC)
        user = User(
            email=email,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
            trial_started_at=trial_started_at,
            trial_ends_at=trial_started_at + timedelta(days=7),
        )
        self._users.add(user)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise EmailAlreadyRegisteredError from error
        return user, self._jwt.create_access_token(user.id)

    async def login(self, *, email: str, password: str) -> tuple[User, str]:
        user = await self._users.get_by_email(email)
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        if not verify_password(password, password_hash) or user is None:
            raise InvalidCredentialsError
        if user.status is not UserStatus.ACTIVE:
            raise InactiveUserError
        return user, self._jwt.create_access_token(user.id)

    async def get_authenticated_user(self, token: str) -> User:
        user_id = self._jwt.decode_access_token(token)
        user = await self._users.get_by_id(user_id)
        if user is None or user.status is not UserStatus.ACTIVE:
            raise InactiveUserError
        return user
