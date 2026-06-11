"""User, address, vendor, and authentication schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str | None = Field(None, pattern=r"^\+?1?\d{9,15}$")


class UserCreate(UserBase):
    """Registration request."""

    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    """Profile update request."""

    full_name: str | None = Field(None, min_length=2, max_length=100)
    phone: str | None = Field(None, pattern=r"^\+?1?\d{9,15}$")


class UserResponse(UserBase):
    model_config = {"from_attributes": True}

    id: UUID
    role: UserRole
    status: UserStatus


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    role: str | None = None
    type: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class EmailVerifyRequest(BaseModel):
    token: str


class GoogleAuthRequest(BaseModel):
    id_token: str


# ---------------------------------------------------------------------------
# Address schemas
# ---------------------------------------------------------------------------

class AddressBase(BaseModel):
    label: str | None = Field(None, max_length=50)
    line1: str = Field(..., min_length=3, max_length=255)
    line2: str | None = Field(None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=4, max_length=20)
    country: str = Field("India", max_length=100)
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    label: str | None = None
    line1: str | None = Field(None, min_length=3, max_length=255)
    line2: str | None = None
    city: str | None = Field(None, min_length=2, max_length=100)
    state: str | None = Field(None, min_length=2, max_length=100)
    postal_code: str | None = Field(None, min_length=4, max_length=20)
    country: str | None = None
    is_default: bool | None = None


class AddressResponse(AddressBase):
    model_config = {"from_attributes": True}
    id: UUID


# ---------------------------------------------------------------------------
# Vendor schemas
# ---------------------------------------------------------------------------

class VendorApplicationRequest(BaseModel):
    business_name: str = Field(..., min_length=3, max_length=255)
    gst_number: str | None = Field(None, max_length=20)


class VendorResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    user_id: UUID
    business_name: str
    gst_number: str | None = None
    is_approved: bool
