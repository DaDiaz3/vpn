import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt.exceptions import InvalidTokenError

from app.core.config import AuthSettings

PASSWORD_HASHER = PasswordHasher()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"


class TokenValidationError(Exception):
    """Raised when a JWT cannot be used as an access token."""


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Use argon2-cffi's constant-time verification implementation."""
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


class JWTService:
    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings

    def create_access_token(self, user_id: uuid.UUID, now: datetime | None = None) -> str:
        issued_at = now or datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=self._settings.access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": expires_at,
            "typ": ACCESS_TOKEN_TYPE,
        }
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> uuid.UUID:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["sub", "iat", "exp", "typ"]},
            )
            if payload["typ"] != ACCESS_TOKEN_TYPE:
                raise TokenValidationError
            return uuid.UUID(payload["sub"])
        except (InvalidTokenError, KeyError, ValueError, TokenValidationError) as error:
            raise TokenValidationError from error
