# backend/core/config.py
import json
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "Payment Service"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me-in-production"

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "payment_db"

    # Bank API
    BANK_API_BASE_URL: str = "https://bank.api"
    BANK_API_TIMEOUT: int = 30
    BANK_API_MAX_RETRIES: int = 3

    # Sync
    SYNC_BANK_PAYMENTS_INTERVAL: int = 300

    # Webhook
    WEBHOOK_SECRET_KEY: str = "change-me-in-production"
    WEBHOOK_TIMEOUT: int = 10
    WEBHOOK_MAX_RETRIES: int = 3
    WEBHOOK_RETRY_DELAY: int = 5

    # Polling
    POLLING_INTERVAL: int = 900
    POLLING_MAX_AGE_MINUTES: int = 30
    POLLING_BATCH_SIZE: int = 100

    # Security
    API_KEY: str = "change-me-in-production"
    API_KEY_HEADER: str = "X-API-Key"
    CORS_ORIGINS: str = "[]"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None

    # Features
    ENABLE_WEBHOOKS: bool = True
    ENABLE_POLLING: bool = True
    ENABLE_METRICS: bool = False
    ENABLE_AUDIT_LOG: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except:
            return []

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
