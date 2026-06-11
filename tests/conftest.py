"""Shared test fixtures for unit and integration tests."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.base import Base


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh async database session for each test."""
    settings = get_settings()
    test_db_url = str(settings.DATABASE_URL).replace("/ecommerce", "/ecommerce_test")
    engine = create_async_engine(test_db_url, echo=False)

    TestSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with TestSessionLocal() as session:
        yield session
        await session.close()

    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """Create an async HTTP client for integration tests.

    Overrides the get_db dependency to use the test session.
    """

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_user_repo():
    """Mock user repository for unit tests."""
    return AsyncMock()


@pytest.fixture
def mock_notification_service():
    """Mock notification service for unit tests."""
    return AsyncMock()


@pytest.fixture
def sample_user_data():
    """Sample user registration data."""
    return {
        "email": f"test-{uuid4().hex[:8]}@example.com",
        "full_name": "Test User",
        "password": "TestPassword123",
        "phone": "+911234567890",
    }


@pytest.fixture
def sample_product_data():
    """Sample product creation data."""
    return {
        "name": "Test Sneaker",
        "sku": f"TST-{uuid4().hex[:6].upper()}",
        "description": "A high-quality test sneaker for running and training.",
        "price": "1299.99",
        "stock": 50,
    }
