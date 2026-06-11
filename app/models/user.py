import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    DECIMAL,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Column,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    VENDOR = "VENDOR"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class UserStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), nullable=False, default=UserRole.CUSTOMER)
    status: Mapped[UserStatus] = mapped_column(String(20), nullable=False, default=UserStatus.UNVERIFIED)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)

    # Google OAuth
    google_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)

    # Relationships
    addresses: Mapped[list["Address"]] = relationship(
        "Address",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    vendor_profile: Mapped["Vendor"] = relationship(
        "Vendor",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_users_email_status", "email", "status"),
    )


class Address(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=True)  # Home, Work, etc.
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="India")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship("User", back_populates="addresses")

    __table_args__ = (
        Index("ix_addresses_user_default", "user_id", "is_default"),
    )


class Vendor(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vendors"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gst_number: Mapped[str] = mapped_column(String(20), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship("User", back_populates="vendor_profile")
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )