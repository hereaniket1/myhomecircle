from fastapi import APIRouter

from app.api.v1.routes import health, root

api_router = APIRouter()
api_router.include_router(root.router)
api_router.include_router(health.router, prefix="/health", tags=["health"])
