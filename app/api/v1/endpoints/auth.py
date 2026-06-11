"""Authentication endpoints — register, login, verify, refresh, password reset."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.common import ApiResponse
from app.schemas.user import (
    EmailVerifyRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    UserCreate,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService

router = APIRouter()


def get_auth_service() -> AuthService:
    """Build AuthService with its dependencies."""
    return AuthService(
        user_repo=UserRepository(),
        notification_service=NotificationService(),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse:
    """Register a new customer account."""
    user = await auth_service.register_user(db, user_in)
    return ApiResponse.success(
        data=UserResponse.model_validate(user),
        message="User registered successfully",
    )


@router.post("/login")
async def login(
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse:
    """Login with email and password to get JWT tokens."""
    token = await auth_service.authenticate(db, login_data)
    return ApiResponse.success(data=token, message="Login successful")


@router.post("/refresh")
async def refresh_token(
    body: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse:
    """Generate new access token from a refresh token."""
    token = await auth_service.refresh_token(db, body.refresh_token)
    return ApiResponse.success(data=token, message="Token refreshed")


@router.post("/verify-email")
async def verify_email(
    body: EmailVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse:
    """Verify email address using the token from the verification email."""
    user = await auth_service.verify_email(db, body.token)
    return ApiResponse.success(
        data=UserResponse.model_validate(user),
        message="Email verified successfully",
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse:
    """Request a password reset email."""
    await auth_service.request_password_reset(db, body.email)
    return ApiResponse.success(
        message="If the email exists, a reset link has been sent.",
    )


@router.post("/reset-password")
async def reset_password(
    body: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse:
    """Reset password using the token from the reset email."""
    await auth_service.reset_password(db, body.token, body.new_password)
    return ApiResponse.success(message="Password has been reset successfully.")


@router.get("/me")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse:
    """Get current user profile."""
    return ApiResponse.success(
        data=UserResponse.model_validate(current_user),
        message="Profile retrieved",
    )
