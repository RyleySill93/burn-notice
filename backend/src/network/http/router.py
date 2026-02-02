from fastapi import APIRouter

from src.app.router import api_router as app_router
from src.network.websockets.router import api_router as websockets_router
from src.platform.router import api_router as platform_router

api_router = APIRouter()
api_router.include_router(platform_router)
api_router.include_router(websockets_router)
api_router.include_router(app_router, prefix='/api')
