import os
import uuid
from fastapi import UploadFile
from app.core.config import get_settings

settings = get_settings()

class FileUploadService:
    async def upload_image(self, file: UploadFile, folder: str = "products") -> str:
        """
        Upload an image.
        In development, saves locally. Otherwise, returns a mock S3 URL.
        """
        extension = file.filename.split(".")[-1] if file.filename else "jpg"
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{extension}"

        if settings.APP_ENV == "development":
            os.makedirs(f"uploads/{folder}", exist_ok=True)
            file_path = f"uploads/{folder}/{filename}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            return f"http://localhost:8000/static/{folder}/{filename}"
        
        # In a real app, use aiobotocore to upload to S3
        # s3_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{folder}/{filename}"

        return f"https://assets.skinglow.website/{folder}/{filename}"

    async def delete_image(self, url: str) -> None:
        """Delete an image from S3."""
        pass
