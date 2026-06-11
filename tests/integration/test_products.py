"""Integration tests for product endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

@pytest.mark.asyncio
async def test_create_category_admin(async_client: AsyncClient, db_session: AsyncSession):
    """Test category creation by admin."""
    # 1. Login as admin (mock or create)
    # For simplicity in this test, we'll assume we can create one
    admin_payload = {
        "email": "admin@skinglow.com",
        "full_name": "Admin User",
        "password": "AdminPassword123"
    }
    await async_client.post("/api/v1/auth/register", json=admin_payload)
    
    # Manually upgrade to admin in DB
    from sqlalchemy import update
    from app.models.user import User, UserRole
    await db_session.execute(
        update(User).where(User.email == admin_payload["email"]).values(role=UserRole.ADMIN)
    )
    await db_session.commit()
    
    # Login
    login_res = await async_client.post("/api/v1/auth/login", data={
        "username": admin_payload["email"],
        "password": admin_payload["password"]
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create category
    cat_payload = {"name": "Skincare", "description": "Skin care products"}
    response = await async_client.post("/api/v1/admin/categories", json=cat_payload, headers=headers)
    
    assert response.status_code == 201
    assert response.json()["name"] == "Skincare"

@pytest.mark.asyncio
async def test_list_products_empty(async_client: AsyncClient):
    """Test listing products when none exist."""
    response = await async_client.get("/api/v1/products/")
    assert response.status_code == 200
    assert response.json()["items"] == []

@pytest.mark.asyncio
async def test_product_lifecycle_vendor(async_client: AsyncClient, db_session: AsyncSession):
    """Test full product lifecycle from vendor perspective."""
    # 1. Register as vendor
    vendor_email = "vendor@example.com"
    vendor_pass = "VendorPass123"
    await async_client.post("/api/v1/auth/register", json={
        "email": vendor_email,
        "full_name": "Vendor User",
        "password": vendor_pass
    })
    
    # Apply for vendor
    login_res = await async_client.post("/api/v1/auth/login", data={
        "username": vendor_email,
        "password": vendor_pass
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    await async_client.post("/api/v1/vendors/apply", json={
        "store_name": "Glow Shop",
        "description": "Best skincare"
    }, headers=headers)
    
    # 2. Admin approves vendor
    # (Reuse admin logic or mock)
    from app.models.user import User, UserRole, Vendor
    from sqlalchemy import select, update
    vendor_query = select(Vendor).join(User).where(User.email == vendor_email)
    vendor = (await db_session.execute(vendor_query)).scalar_one()
    vendor.is_approved = True
    user = (await db_session.execute(select(User).where(User.email == vendor_email))).scalar_one()
    user.role = UserRole.VENDOR
    await db_session.commit()
    
    # 3. Create category (Admin)
    from app.models.product import Category
    cat = Category(name="Serums", slug="serums")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    
    # 4. Vendor lists product
    product_payload = {
        "name": "Vitamin C Serum",
        "description": "Brightening serum for all skin types.",
        "price": "1499.00",
        "stock": 100,
        "category_id": str(cat.id),
        "sku": "VIT-C-001"
    }
    response = await async_client.post("/api/v1/products/", json=product_payload, headers=headers)
    assert response.status_code == 201
    product_id = response.json()["id"]
    
    # 5. Verify product is PENDING and not in public list
    list_res = await async_client.get("/api/v1/products/")
    assert not any(p["id"] == product_id for p in list_res.json()["items"])
    
    # 6. Admin approves product
    # (Mock admin login or use existing logic)
    # Actually, we can just update DB directly for speed in integration test if endpoint logic is already tested elsewhere
    from app.models.product import Product, ProductStatus
    await db_session.execute(
        update(Product).where(Product.id == UUID(product_id)).values(status=ProductStatus.ACTIVE)
    )
    await db_session.commit()
    
    # 7. Verify product is now public
    list_res = await async_client.get("/api/v1/products/")
    assert any(p["id"] == product_id for p in list_res.json()["items"])
