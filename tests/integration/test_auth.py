"""Integration tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_password
from app.models.user import User

@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient, db_session: AsyncSession):
    """Test successful user registration."""
    payload = {
        "email": "newuser@example.com",
        "full_name": "New User",
        "password": "StrongPassword123!",
        "phone": "+919876543210"
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data
    assert "password" not in data

@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient, db_session: AsyncSession):
    """Test registration with an already existing email."""
    # First registration
    payload = {
        "email": "dup@example.com",
        "full_name": "First User",
        "password": "Password123!"
    }
    await async_client.post("/api/v1/auth/register", json=payload)
    
    # Second registration with same email
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, db_session: AsyncSession):
    """Test successful login and JWT generation."""
    # Register first
    email = "login@example.com"
    password = "CorrectPassword123"
    await async_client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Login User",
        "password": password
    })
    
    # Login
    response = await async_client.post("/api/v1/auth/login", data={
        "username": email,
        "password": password
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient, db_session: AsyncSession):
    """Test login with wrong password."""
    email = "wrongpass@example.com"
    await async_client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Test User",
        "password": "CorrectPassword"
    })
    
    response = await async_client.post("/api/v1/auth/login", data={
        "username": email,
        "password": "WrongPassword"
    })
    
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()
