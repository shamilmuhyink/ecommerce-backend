"""Product and category schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.product import ProductStatus


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    image_url: str | None = None


class CategoryCreate(CategoryBase):
    parent_id: UUID | None = None


class CategoryResponse(CategoryBase):
    model_config = {"from_attributes": True}

    id: UUID
    parent_id: UUID | None = None


class ProductVariantBase(BaseModel):
    sku: str = Field(..., pattern=r"^[A-Z0-9\-]{4,20}$")
    size: str | None = None
    color: str | None = None
    material: str | None = None
    stock: int = Field(..., ge=0)
    price: Decimal | None = Field(None, gt=0.0)


class ProductVariantResponse(ProductVariantBase):
    model_config = {"from_attributes": True}
    id: UUID


class ProductBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    sku: str = Field(..., pattern=r"^[A-Z0-9\-]{4,20}$")
    description: str = Field(..., min_length=10)
    price: Decimal = Field(..., gt=0.0)
    compare_at_price: Decimal | None = Field(None, gt=0.0)
    stock: int = Field(..., ge=0)
    category_id: UUID


class ProductCreate(ProductBase):
    images: str | None = None
    variants: list[ProductVariantBase] = []


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, min_length=10)
    price: Decimal | None = Field(None, gt=0.0)
    compare_at_price: Decimal | None = Field(None, gt=0.0)
    stock: int | None = Field(None, ge=0)
    status: ProductStatus | None = None


class ProductResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    sku: str
    description: str
    price: Decimal
    compare_at_price: Decimal | None = None
    stock: int
    status: ProductStatus
    vendor_id: UUID
    category_id: UUID
    images: list[str] | None = None
    variants: list[ProductVariantResponse] = []
    created_at: datetime | None = None

    @field_validator("images", mode="before")
    @classmethod
    def parse_images(cls, v: str | list | None) -> list[str] | None:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v
