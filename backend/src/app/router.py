from fastapi import APIRouter

from src.app.engineers.router import router as engineers_router
from src.app.github.router import router as github_router
from src.app.leaderboard.router import router as leaderboard_router
from src.app.usage.router import router as usage_router

# Create the root API router
api_router = APIRouter()

# Include domain routers
api_router.include_router(engineers_router, prefix='/engineers', tags=['engineers'])
api_router.include_router(usage_router, prefix='/usage', tags=['usage'])
api_router.include_router(leaderboard_router, prefix='/leaderboard', tags=['leaderboard'])
api_router.include_router(github_router, tags=['github'])
