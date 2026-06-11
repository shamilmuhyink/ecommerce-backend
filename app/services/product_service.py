"""Product management service."""

from collections.abc import Sequence
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateError, NotFoundError, ValidationError
from app.models.product import Product, ProductStatus
from app.repositories.product_repository import (
    CategoryRepository,
    ProductRepository,
    ProductVariantRepository,
)
from app.schemas.product import ProductCreate, ProductUpdate

logger = structlog.get_logger(__name__)


class ProductService:
    """Product CRUD, status management, and search."""

    def __init__(
        self,
        product_repo: ProductRepository,
        variant_repo: ProductVariantRepository,
        category_repo: CategoryRepository,
    ) -> None:
        self._product_repo = product_repo
        self._variant_repo = variant_repo
        self._category_repo = category_repo

    async def create_product(
        self,
        db: AsyncSession,
        vendor_id: UUID,
        product_in: ProductCreate,
    ) -> Product:
        """Create a new product with optional variants.

        Products start in PENDING status and require admin approval.

        Raises:
            NotFoundError: If category does not exist.
        """
        # Validate category exists
        category = await self._category_repo.get(db, product_in.category_id)
        if not category:
            raise NotFoundError("Category", str(product_in.category_id))

        product_data = product_in.model_dump(exclude={"variants"})
        product_data["vendor_id"] = vendor_id
        product_data["status"] = ProductStatus.PENDING

        try:
            product = await self._product_repo.create(db, obj_in=product_data)

            # Create variants
            for variant_in in product_in.variants:
                variant_data = variant_in.model_dump()
                variant_data["product_id"] = product.id
                await self._variant_repo.create(db, obj_in=variant_data)

            # Re-fetch product to ensure relationships (variants, category) are eager-loaded
            product_with_details = await self._product_repo.get_with_details(db, product.id)
            if product_with_details:
                product = product_with_details
        except IntegrityError as e:
            await db.rollback()
            raise DuplicateError("Product or Variant", "sku", product_in.sku) from e
        logger.info(
            "product_created",
            product_id=str(product.id),
            vendor_id=str(vendor_id),
            sku=product.sku,
        )
        return product

    async def get_product(self, db: AsyncSession, product_id: UUID) -> Product:
        """Fetch a single product with details.

        Raises:
            NotFoundError: If product does not exist.
        """
        product = await self._product_repo.get_with_details(db, product_id)
        if not product:
            raise NotFoundError("Product", str(product_id))
        return product

    async def list_active_products(
        self,
        db: AsyncSession,
        *,
        category_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Product], int]:
        """Fetch paginated active products for the storefront."""
        return await self._product_repo.get_active(db, category_id=category_id, skip=skip, limit=limit)

    async def update_product(
        self,
        db: AsyncSession,
        product_id: UUID,
        vendor_id: UUID,
        product_in: ProductUpdate,
    ) -> Product:
        """Update product details (vendor can only update their own products).

        Raises:
            NotFoundError: If product does not exist.
            ValidationError: If vendor does not own the product.
        """
        product = await self._product_repo.get(db, product_id)
        if not product:
            raise NotFoundError("Product", str(product_id))

        if product.vendor_id != vendor_id:
            raise ValidationError("You can only update your own products")

        update_data = product_in.model_dump(exclude_unset=True)
        updated = await self._product_repo.update(
            db, db_obj=product, obj_in=update_data
        )
        logger.info("product_updated", product_id=str(product_id))
        return updated

    async def search_products(
        self,
        db: AsyncSession,
        query: str,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Product], int]:
        """Search products by name/description."""
        return await self._product_repo.search(db, query, skip=skip, limit=limit)

    async def approve_product(self, db: AsyncSession, product_id: UUID) -> Product:
        """Admin approves a pending product.

        Raises:
            NotFoundError: If product does not exist.
        """
        product = await self._product_repo.update_status(
            db, product_id, ProductStatus.ACTIVE
        )
        if not product:
            raise NotFoundError("Product", str(product_id))

        await db.commit()
        logger.info("product_approved", product_id=str(product_id))
        return product

    async def reject_product(
        self, db: AsyncSession, product_id: UUID, reason: str
    ) -> Product:
        """Admin rejects a pending product.

        Raises:
            NotFoundError: If product does not exist.
        """
        product = await self._product_repo.update_status(
            db, product_id, ProductStatus.REJECTED
        )
        if not product:
            raise NotFoundError("Product", str(product_id))

        await db.commit()
        logger.info(
            "product_rejected", product_id=str(product_id), reason=reason
        )
        return product
