"""Address endpoints — CRUD for user shipping addresses."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.user_repository import AddressRepository
from app.schemas.common import ApiResponse
from app.schemas.user import AddressCreate, AddressResponse, AddressUpdate

router = APIRouter()


@router.get("")
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """List all addresses for the current user."""
    repo = AddressRepository()
    addresses = await repo.get_by_user(db, current_user.id)
    return ApiResponse.success(
        data=[AddressResponse.model_validate(a) for a in addresses],
        message="Addresses retrieved",
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_address(
    body: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Add a new shipping address."""
    repo = AddressRepository()
    if body.is_default:
        await repo.clear_defaults(db, current_user.id)

    data = body.model_dump()
    data["user_id"] = current_user.id
    address = await repo.create(db, obj_in=data)
    return ApiResponse.success(
        data=AddressResponse.model_validate(address),
        message="Address created successfully",
    )


@router.patch("/{address_id}")
async def update_address(
    address_id: UUID,
    body: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Update an existing address."""
    repo = AddressRepository()
    address = await repo.get(db, address_id)
    if not address or address.user_id != current_user.id:
        raise NotFoundError("Address", str(address_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data.get("is_default"):
        await repo.clear_defaults(db, current_user.id)

    updated = await repo.update(db, db_obj=address, obj_in=update_data)
    return ApiResponse.success(
        data=AddressResponse.model_validate(updated),
        message="Address updated successfully",
    )


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove an address."""
    repo = AddressRepository()
    address = await repo.get(db, address_id)
    if not address or address.user_id != current_user.id:
        raise NotFoundError("Address", str(address_id))
    await repo.remove(db, id=address_id)
