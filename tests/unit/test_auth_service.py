"""Unit tests for auth service."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.core.exceptions import AuthenticationError, DuplicateError
from app.models.user import User, UserStatus
from app.schemas.user import LoginRequest, UserCreate
from app.services.auth_service import AuthService


@pytest.fixture
def auth_service():
    return AuthService(
        user_repo=AsyncMock(),
        notification_service=AsyncMock(),
    )


class TestRegisterUser:
    async def test_raises_when_email_exists(self, auth_service: AuthService) -> None:
        auth_service._user_repo.get_by_email.return_value = MagicMock(spec=User)
        user_in = UserCreate(
            email="existing@example.com",
            full_name="Test User",
            password="TestPass123",
        )
        with pytest.raises(DuplicateError):
            await auth_service.register_user(AsyncMock(), user_in)

    async def test_creates_user_when_email_is_new(self, auth_service: AuthService) -> None:
        auth_service._user_repo.get_by_email.return_value = None
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        mock_user.email = "new@example.com"
        auth_service._user_repo.create.return_value = mock_user

        user_in = UserCreate(
            email="new@example.com",
            full_name="New User",
            password="TestPass123",
        )
        result = await auth_service.register_user(AsyncMock(), user_in)
        assert result == mock_user
        auth_service._user_repo.create.assert_awaited_once()
        auth_service._notification_service.enqueue_registration_email.assert_awaited_once()


class TestAuthenticate:
    async def test_raises_on_wrong_password(self, auth_service: AuthService) -> None:
        auth_service._user_repo.get_by_email.return_value = None
        login_data = LoginRequest(email="test@example.com", password="wrong")
        with pytest.raises(AuthenticationError, match="Incorrect email"):
            await auth_service.authenticate(AsyncMock(), login_data)

    async def test_raises_on_suspended_account(self, auth_service: AuthService) -> None:
        mock_user = MagicMock(spec=User)
        mock_user.status = UserStatus.SUSPENDED
        mock_user.password_hash = "$2b$12$test"
        auth_service._user_repo.get_by_email.return_value = mock_user
        # Patch verify_password to return True
        import app.services.auth_service as module
        original = module.verify_password
        module.verify_password = lambda p, h: True
        try:
            with pytest.raises(AuthenticationError, match="suspended"):
                await auth_service.authenticate(
                    AsyncMock(), LoginRequest(email="t@t.com", password="x")
                )
        finally:
            module.verify_password = original
