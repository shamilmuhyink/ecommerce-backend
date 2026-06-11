"""V1 API router aggregator — all endpoint modules registered here."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    addresses,
    admin,
    auth,
    cart,
    coupons,
    orders,
    payments,
    products,
    returns,
    upload,
    vendors,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(addresses.router, prefix="/addresses", tags=["addresses"])
api_router.include_router(coupons.router, prefix="/coupons", tags=["coupons"])
api_router.include_router(returns.router, prefix="/returns", tags=["returns"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
