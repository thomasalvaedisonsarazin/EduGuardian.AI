"""audit endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/audit-logs", tags=["audit"])
