"""Application settings loaded from environment variables / .env files."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"  # dev default only; override via env


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden by an env var of the same name."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "EduGuardian AI"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+psycopg://edu:edu@localhost:5432/eduguardian"

    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_ENABLED: bool = False
    LLM_MONTHLY_BUDGET_USD: float = 15.0

    REPORTS_DIR: str = "./data/reports"
    UPLOADS_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 5

    # --- Module 5: LLM cost control & agent runs ---
    # USD per 1M tokens for OPENAI_MODEL. Defaults match gpt-4o-mini list prices at the time of
    # writing - they MUST be checked against current OpenAI pricing before going live.
    LLM_INPUT_PRICE_PER_MTOK: float = 0.15
    LLM_OUTPUT_PRICE_PER_MTOK: float = 0.60
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 1
    LLM_MAX_OUTPUT_TOKENS: int = 4000
    LLM_BATCH_SIZE: int = 8  # at-risk students per intervention-drafting LLM call

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def llm_available(self) -> bool:
        """True only when the LLM is enabled AND an API key is configured."""
        return self.LLM_ENABLED and bool(self.OPENAI_API_KEY)

    def warn_insecure_defaults(self) -> None:
        """Log a warning for unsafe configuration (called at app startup)."""
        if self.SECRET_KEY == DEV_SECRET_KEY and self.is_production:
            logger.warning("SECRET_KEY is the development default in production - set it!")


settings = Settings()
