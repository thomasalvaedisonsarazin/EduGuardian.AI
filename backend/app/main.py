"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import settings
from app.exceptions import AppError
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def error_body(code: str, message: str, details: object | None = None) -> dict[str, object]:
    """Standard error envelope: {"error": {"code", "message"[, "details"]}}."""
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.warn_insecure_defaults()
    for directory in (settings.REPORTS_DIR, settings.UPLOADS_DIR):
        Path(directory).mkdir(parents=True, exist_ok=True)
    logger.info("%s starting (env=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    lifespan=lifespan,
    # Interactive API docs are a development aid; don't advertise the API surface publicly.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- exception handlers ---
@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(f"HTTP_{exc.status_code}", str(exc.detail)),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Request validation failed", details),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500, content=error_body("INTERNAL_ERROR", "An unexpected error occurred")
    )


# --- health ---
@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/db", tags=["health"])
def health_db() -> JSONResponse:
    from app.database import engine  # lazy: /health must not depend on the DB module

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return JSONResponse(
            status_code=503, content={"status": "unhealthy", "database": "unreachable"}
        )
    return JSONResponse(content={"status": "healthy", "database": "ok"})


# --- routers ---
# Phase 2 agents: import routers and register them here, e.g.
#   from app.routers import auth
#   app.include_router(auth.router, prefix="/api/v1")
from app.routers import (  # noqa: E402
    agent_runs,
    analytics,
    audit,
    auth,
    imports,
    interventions,
    reports,
    schools,
    setup,
)

for _module in (
    auth,
    schools,
    setup,
    imports,
    analytics,
    agent_runs,
    interventions,
    audit,
    reports,
):
    app.include_router(_module.router, prefix="/api/v1")
