"""User and vendor repository with domain-specific queries."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, Vendor, Address
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self) -> None:
        super().__init__(User)

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        """Fetch user by email address."""
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_google_id(self, db: AsyncSession, google_id: str) -> User | None:
        """Fetch user by Google OAuth ID."""
        query = select(User).where(User.google_id == google_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_addresses(self, db: AsyncSession, user_id: UUID) -> User | None:
        """Fetch user with eagerly loaded addresses."""
        query = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.addresses))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_vendor(self, db: AsyncSession, user_id: UUID) -> User | None:
        """Fetch user with eagerly loaded vendor profile."""
        query = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.vendor_profile))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count(self, db: AsyncSession) -> int:
        """Count total users."""
        result = await db.execute(select(func.count(User.id)))
        return result.scalar_one()


class VendorRepository(BaseRepository[Vendor]):
    def __init__(self) -> None:
        super().__init__(Vendor)

    async def get_by_user_id(self, db: AsyncSession, user_id: UUID) -> Vendor | None:
        """Fetch vendor profile by user ID."""
        query = select(Vendor).where(Vendor.user_id == user_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_pending_vendors(self, db: AsyncSession) -> list[Vendor]:
        """Fetch all vendors pending approval."""
        query = select(Vendor).where(Vendor.is_approved == False)  # noqa: E712
        result = await db.execute(query)
        return list(result.scalars().all())


class AddressRepository(BaseRepository[Address]):
    def __init__(self) -> None:
        super().__init__(Address)

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> list[Address]:
        """Fetch all addresses for a user."""
        query = select(Address).where(Address.user_id == user_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_default(self, db: AsyncSession, user_id: UUID) -> Address | None:
        """Fetch the user's default address."""
        query = select(Address).where(
            Address.user_id == user_id, Address.is_default == True  # noqa: E712
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def clear_defaults(self, db: AsyncSession, user_id: UUID) -> None:
        """Reset is_default for all user addresses (before setting a new one)."""
        addresses = await self.get_by_user(db, user_id)
        for addr in addresses:
            addr.is_default = False
        await db.flush()
