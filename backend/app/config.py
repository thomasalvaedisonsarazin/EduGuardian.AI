"""Application settings loaded from environment variables / .env files."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"  # dev default only; override via env
#: Placeholder keys shipped in .env.example / docker-compose; never acceptable in production.
KNOWN_WEAK_SECRET_KEYS = frozenset({DEV_SECRET_KEY, "change-me", "your-secret-key", "secret"})
MIN_SECRET_KEY_LENGTH = 32


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

    @property
    def secret_key_is_weak(self) -> bool:
        key = self.SECRET_KEY.strip()
        return key in KNOWN_WEAK_SECRET_KEYS or len(key) < MIN_SECRET_KEY_LENGTH

    def warn_insecure_defaults(self) -> None:
        """Check for unsafe configuration (called at app startup).

        A weak/placeholder SECRET_KEY lets anyone forge access tokens for any user, so it is a
        hard error in production and a warning elsewhere.
        """
        if not self.secret_key_is_weak:
            return
        if self.is_production:
            raise RuntimeError(
                "SECRET_KEY is a placeholder or shorter than "
                f"{MIN_SECRET_KEY_LENGTH} characters - refusing to start in production"
            )
        logger.warning("SECRET_KEY is weak or a placeholder - set a strong value before deploying")


settings = Settings()
