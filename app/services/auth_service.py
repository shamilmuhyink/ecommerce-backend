"""Authentication service — registration, login, verification, password reset.

Services raise AppException subclasses, never HTTPException.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    DuplicateError,
    NotFoundError,
)
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.user import LoginRequest, Token, UserCreate
from app.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)


class AuthService:
    """Handles user registration, login, email verification, and password reset."""

    def __init__(
        self,
        user_repo: UserRepository,
        notification_service: NotificationService,
    ) -> None:
        self._user_repo = user_repo
        self._notification_service = notification_service

    async def register_user(self, db: AsyncSession, user_in: UserCreate) -> User:
        """Register a new customer account.

        Raises:
            DuplicateError: If email is already registered.
        """
        existing = await self._user_repo.get_by_email(db, user_in.email)
        if existing:
            raise DuplicateError("User", "email", user_in.email)

        user_data = user_in.model_dump(exclude={"password"})
        user_data["password_hash"] = hash_password(user_in.password)
        user_data["status"] = UserStatus.UNVERIFIED

        user = await self._user_repo.create(db, obj_in=user_data)
        logger.info("user_registered", user_id=str(user.id), email=user.email)

        # Send verification email
        token = create_verification_token(str(user.id))
        await self._notification_service.enqueue_registration_email(user, token)

        return user

    async def authenticate(self, db: AsyncSession, login_data: LoginRequest) -> Token:
        """Authenticate with email/password and return JWT tokens.

        Raises:
            AuthenticationError: If credentials are invalid.
            AuthenticationError: If account is suspended.
        """
        user = await self._user_repo.get_by_email(db, login_data.email)
        if not user or not verify_password(login_data.password, user.password_hash):
            raise AuthenticationError("Incorrect email or password")

        if user.status == UserStatus.SUSPENDED:
            raise AuthenticationError("Account is suspended")

        if user.status == UserStatus.DELETED:
            raise AuthenticationError("Account not found")

        access_token = create_access_token(subject=str(user.id), role=user.role)
        refresh_token = create_refresh_token(subject=str(user.id))

        logger.info("user_authenticated", user_id=str(user.id))

        return Token(access_token=access_token, refresh_token=refresh_token)

    async def refresh_token(self, db: AsyncSession, refresh_token_str: str) -> Token:
        """Generate new access token from a valid refresh token.

        Raises:
            AuthenticationError: If refresh token is invalid or expired.
        """
        try:
            payload = decode_token(refresh_token_str)
        except ValueError:
            raise AuthenticationError("Invalid refresh token")

        if payload.type != "refresh" or not payload.sub:
            raise AuthenticationError("Invalid token type")

        from uuid import UUID

        user = await self._user_repo.get(db, UUID(payload.sub))
        if not user or user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
            raise AuthenticationError("Account not available")

        access_token = create_access_token(subject=str(user.id), role=user.role)
        new_refresh = create_refresh_token(subject=str(user.id))

        return Token(access_token=access_token, refresh_token=new_refresh)

    async def verify_email(self, db: AsyncSession, token: str) -> User:
        """Verify user email from verification token.

        Raises:
            AuthenticationError: If token is invalid or expired.
        """
        try:
            payload = decode_token(token)
        except ValueError:
            raise AuthenticationError("Invalid or expired verification token")

        if payload.type != "verify" or not payload.sub:
            raise AuthenticationError("Invalid token type")

        from uuid import UUID

        user = await self._user_repo.get(db, UUID(payload.sub))
        if not user:
            raise NotFoundError("User", payload.sub)

        if user.status == UserStatus.ACTIVE:
            return user  # Already verified

        await self._user_repo.update(db, db_obj=user, obj_in={"status": UserStatus.ACTIVE})
        logger.info("email_verified", user_id=str(user.id))
        return user

    async def request_password_reset(self, db: AsyncSession, email: str) -> None:
        """Send password reset email. Always succeeds to prevent email enumeration."""
        user = await self._user_repo.get_by_email(db, email)
        if not user:
            return  # Don't reveal whether email exists

        token = create_password_reset_token(str(user.id))
        await self._notification_service.enqueue_password_reset_email(user, token)
        logger.info("password_reset_requested", user_id=str(user.id))

    async def reset_password(self, db: AsyncSession, token: str, new_password: str) -> None:
        """Reset password using a reset token.

        Raises:
            AuthenticationError: If token is invalid or expired.
        """
        try:
            payload = decode_token(token)
        except ValueError:
            raise AuthenticationError("Invalid or expired reset token")

        if payload.type != "reset" or not payload.sub:
            raise AuthenticationError("Invalid token type")

        from uuid import UUID

        user = await self._user_repo.get(db, UUID(payload.sub))
        if not user:
            raise NotFoundError("User", payload.sub)

        new_hash = hash_password(new_password)
        await self._user_repo.update(db, db_obj=user, obj_in={"password_hash": new_hash})
        logger.info("password_reset_completed", user_id=str(user.id))
