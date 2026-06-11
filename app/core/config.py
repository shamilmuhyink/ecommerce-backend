import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    All configuration MUST be accessed via get_settings(). Never instantiate
    Settings() directly or use os.environ anywhere else in the codebase.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    APP_NAME: str = "Ecommerce API"
    APP_ENV: str = "development"  # Default if not found
    DEBUG: bool = False
    SECRET_KEY: str = Field(...)  # min 32 chars, loaded from env
    ALLOWED_ORIGINS: list[str] = []
    FRONTEND_URL: str = "https://glowey.com"

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: RedisDsn

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AWS
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET: str = Field(...)
    AWS_SES_SENDER: str = Field(...)

    # Resend (Staging Only)
    RESEND_API_KEY: str = ""
    RESEND_SENDER: str = ""

    # Payment Gateway
    RAZORPAY_KEY_ID: str = Field(...)
    RAZORPAY_KEY_SECRET: str = Field(...)
    RAZORPAY_WEBHOOK_SECRET: str = Field(...)

    # Shipping
    SHIPROCKET_EMAIL: str = Field(...)
    SHIPROCKET_PASSWORD: str = Field(...)

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "testing"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    # Get the directory of the current file (app/core)
    # Then go up two levels to reach the backend root
    root_dir = Path(__file__).resolve().parent.parent.parent

    # 1. Look for APP_ENV in current environment
    # 2. If not found, try loading base .env using absolute path
    base_env = root_dir / ".env"
    load_dotenv(base_env)
    env = os.getenv("APP_ENV", "development")

    # 3. Load the environment-specific file using absolute path
    env_file = root_dir / f".env.{env}"

    # If the specific file doesn't exist, fall back to base .env
    if not env_file.exists():
        env_file = base_env

    return Settings(_env_file=str(env_file))
