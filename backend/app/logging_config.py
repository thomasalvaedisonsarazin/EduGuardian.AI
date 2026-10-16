"""Central logging configuration."""

import logging.config

from app.config import settings


def setup_logging(level: str | None = None) -> None:
    """Configure root logging (safe to call more than once)."""
    log_level = (level or settings.LOG_LEVEL).upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"},
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default"},
            },
            "root": {"level": log_level, "handlers": ["console"]},
            "loggers": {
                "sqlalchemy.engine": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
            },
        }
    )
