"""Product, category, and variant repository with domain queries."""

from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Category, Product, ProductStatus, ProductVariant
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self) -> None:
        super().__init__(Product)

    async def get_with_details(self, db: AsyncSession, id: UUID) -> Product | None:
        """Fetch product with variants and category eagerly loaded."""
        query = (
            select(Product)
            .where(Product.id == id)
            .options(selectinload(Product.variants), selectinload(Product.category))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_active(
        self,
        db: AsyncSession,
        *,
        category_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Product], int]:
        """Fetch active products with total count for pagination."""
        base = select(Product).where(Product.status == ProductStatus.ACTIVE)
        if category_id:
            base = base.where(Product.category_id == category_id)

        count_query = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = (
            base.order_by(Product.created_at.desc())
            .offset(skip)
            .limit(limit)
            .options(selectinload(Product.variants))
        )
        result = await db.execute(query)
        return result.scalars().all(), total

    async def get_by_category(
        self, db: AsyncSession, category_id: UUID
    ) -> Sequence[Product]:
        """Fetch all active products in a category."""
        query = select(Product).where(
            Product.category_id == category_id,
            Product.status == ProductStatus.ACTIVE,
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_vendor(
        self, db: AsyncSession, vendor_id: UUID
    ) -> Sequence[Product]:
        """Fetch all products owned by a vendor."""
        query = (
            select(Product)
            .where(Product.vendor_id == vendor_id)
            .order_by(Product.created_at.desc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_status(
        self, db: AsyncSession, status: ProductStatus
    ) -> Sequence[Product]:
        """Fetch products by status (for admin review)."""
        query = select(Product).where(Product.status == status)
        result = await db.execute(query)
        return result.scalars().all()

    async def update_status(
        self, db: AsyncSession, id: UUID, status: ProductStatus
    ) -> Product | None:
        """Update product status (approve/reject/deactivate)."""
        product = await self.get(db, id)
        if product:
            product.status = status
            db.add(product)
            await db.flush()
        return product

    async def search(
        self,
        db: AsyncSession,
        query_str: str,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Product], int]:
        """Simple text search on product name and description."""
        pattern = f"%{query_str}%"
        base = select(Product).where(
            Product.status == ProductStatus.ACTIVE,
            (Product.name.ilike(pattern) | Product.description.ilike(pattern)),
        )

        count_query = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = base.order_by(Product.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all(), total


class CategoryRepository(BaseRepository[Category]):
    def __init__(self) -> None:
        super().__init__(Category)

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Category | None:
        """Fetch category by URL slug."""
        query = select(Category).where(Category.slug == slug)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, db: AsyncSession) -> Sequence[Category]:
        """Fetch all categories."""
        query = select(Category).order_by(Category.name)
        result = await db.execute(query)
        return result.scalars().all()


class ProductVariantRepository(BaseRepository[ProductVariant]):
    def __init__(self) -> None:
        super().__init__(ProductVariant)
