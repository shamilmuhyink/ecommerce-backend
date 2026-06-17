import os
import uuid

import aiobotocore.session
from botocore.config import Config
from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()


class FileUploadService:
    def __init__(self) -> None:
        self.session = aiobotocore.session.get_session()

    async def upload_image(self, file: UploadFile, folder: str = "products") -> str:
        """
        Upload an image.
        Staging: Streams to OCI Object Storage.
        Production: Uses AWS S3 (currently mocked).
        Development: Saves locally.
        """
        extension = file.filename.split(".")[-1] if file.filename else "jpg"
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{extension}"

        if settings.APP_ENV == "staging":
            # Upload to OCI Object Storage
            content = await file.read()
            key = f"{folder}/{filename}"
            async with self.session.create_client(
                "s3",
                endpoint_url=settings.OCI_S3_ENDPOINT_URL,
                aws_access_key_id=settings.OCI_S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.OCI_S3_SECRET_ACCESS_KEY,
                region_name=settings.OCI_S3_REGION_NAME,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            ) as client:
                await client.put_object(
                    Bucket=settings.OCI_S3_BUCKET_NAME,
                    Key=key,
                    Body=content,
                    ContentType=file.content_type or "application/octet-stream",
                )
            return f"{settings.OCI_S3_PUBLIC_URL_PREFIX.rstrip('/')}/{key}"

        elif settings.APP_ENV == "production":
            # In a real app, use aiobotocore to upload to AWS S3
            # s3_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{folder}/{filename}"
            return f"https://api.skinglow.website/{folder}/{filename}"

        else:
            # Local/Development fallback
            os.makedirs(f"uploads/{folder}", exist_ok=True)
            file_path = f"uploads/{folder}/{filename}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            return f"http://localhost:8000/static/{folder}/{filename}"

    async def delete_image(self, url: str) -> None:
        """Delete an image depending on the environment."""
        if settings.APP_ENV == "staging":
            prefix = settings.OCI_S3_PUBLIC_URL_PREFIX.rstrip("/")
            if url.startswith(prefix):
                key = url[len(prefix) + 1 :]
                async with self.session.create_client(
                    "s3",
                    endpoint_url=settings.OCI_S3_ENDPOINT_URL,
                    aws_access_key_id=settings.OCI_S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.OCI_S3_SECRET_ACCESS_KEY,
                    region_name=settings.OCI_S3_REGION_NAME,
                    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
                ) as client:
                    await client.delete_object(Bucket=settings.OCI_S3_BUCKET_NAME, Key=key)
        elif settings.APP_ENV == "production":
            # Handle S3 deletion
            pass
        else:
            # Handle local deletion
            try:
                path_part = url.split("/static/")[-1]
                file_path = f"uploads/{path_part}"
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
