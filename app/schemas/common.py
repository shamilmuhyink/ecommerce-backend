"""Common schemas: standard API response envelope, pagination, error details."""

from math import ceil
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    page: int
    limit: int
    total: int
    total_pages: int


class PaginationParams(BaseModel):
    """Query parameters for all paginated endpoints."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field(default="desc", pattern="^(asc|desc)$")


# ---------------------------------------------------------------------------
# Error detail
# ---------------------------------------------------------------------------


class ApiError(BaseModel):
    """Structured error detail for validation and business rule failures."""

    code: str
    field: str | None = None
    message: str


# ---------------------------------------------------------------------------
# Standard API response envelope
# ---------------------------------------------------------------------------


def _success_impl(
    cls: type["ApiResponse"],
    data: Any = None,
    message: str = "Success",
) -> "ApiResponse":
    return cls(success=True, data=data, message=message, meta=None, errors=None)


class ApiResponse(BaseModel, Generic[T]):
    """Standard envelope for ALL API responses.

    Usage:
        ApiResponse.success(data=user, message="User created")
        ApiResponse.paginated(items=products, total=100, page=1, page_size=20)
        ApiResponse.error(message="Not found", errors=[...])
    """

    success: bool
    data: T | None = None
    message: str | None = None
    meta: PaginationMeta | None = None
    errors: list[ApiError] | None = None

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "Success",
    ) -> "ApiResponse":
        return _success_impl(cls, data, message)

    @classmethod
    def paginated(
        cls,
        items: list[Any],
        total: int,
        page: int = 1,
        page_size: int = 20,
        message: str = "Success",
    ) -> "ApiResponse":
        total_pages = ceil(total / page_size) if total > 0 else 0
        return cls(
            success=True,
            data=items,
            message=message,
            meta=PaginationMeta(
                page=page,
                limit=page_size,
                total=total,
                total_pages=total_pages,
            ),
            errors=None,
        )

    @classmethod
    def error(
        cls,
        message: str = "An error occurred",
        errors: list[ApiError] | None = None,
    ) -> "ApiResponse":
        return cls(success=False, data=None, message=message, meta=None, errors=errors)


# Re-bind the success classmethod after class creation to bypass Pydantic's runtime field-masking.
ApiResponse.success = classmethod(_success_impl)