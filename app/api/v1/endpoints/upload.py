"""File upload endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.security import require_role
from app.models.user import User, UserRole
from app.schemas.common import ApiResponse
from app.utils.file_upload import FileUploadService

router = APIRouter()


@router.post("/image")
async def upload_image(
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    file: UploadFile = File(...),  # noqa: B008
    folder: str = Form("products"),
) -> ApiResponse:
    """Upload an image to storage and return its public URL."""
    service = FileUploadService()
    url = await service.upload_image(file, folder=folder)
    return ApiResponse.success(
        data={"url": url},
        message="Image uploaded successfully",
    )
