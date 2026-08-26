# app/api/v1/router.py

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.tz_check import router as tz_check_router

api_router = APIRouter()

api_router.include_router(
    health_router
)

api_router.include_router(
    tz_check_router
)
