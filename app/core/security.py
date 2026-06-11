"""JWT, hashing, token utilities, and RBAC dependency injection."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.user import TokenPayload

settings = get_settings()


reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


def create_access_token(subject: str, role: str) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_verification_token(subject: str) -> str:
    """Create a 24-hour email verification token."""
    expire = datetime.now(UTC) + timedelta(hours=24)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "verify",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_password_reset_token(subject: str) -> str:
    """Create a 15-minute password reset token."""
    expire = datetime.now(UTC) + timedelta(minutes=15)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "reset",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds)."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token, returning typed payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return TokenPayload(
            sub=payload.get("sub"),
            role=payload.get("role"),
            type=payload.get("type"),
        )
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")


def get_user_id_from_token(token: str) -> UUID:
    """Extract user UUID from a JWT token."""
    payload = decode_token(token)
    if not payload.sub:
        raise ValueError("Token does not contain user ID")
    return UUID(payload.sub)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(reusable_oauth2)],
) -> "User":
    """FastAPI dependency that extracts and validates the current user from JWT."""
    try:
        token_data = decode_token(token)
        if token_data.sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        if token_data.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except (ValueError, JWTError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository()
    user = await user_repo.get_with_vendor(db, UUID(token_data.sub))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.models.user import UserStatus

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(status_code=403, detail="Account is suspended")
    if user.status == UserStatus.DELETED:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def require_role(*roles: "UserRole"):
    """Factory that returns a dependency enforcing one of the given roles.

    Usage:
        @router.patch("/products/{id}/approve")
        async def approve_product(
            admin: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
        ):
    """

    async def _check(current_user: "User" = Depends(get_current_user)) -> "User":
        from app.models.user import UserRole as UserRoleEnum

        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation.",
            )
        return current_user

    return _check


# Import types for forward references
from app.models.user import User, UserRole  # noqa: E402, F401