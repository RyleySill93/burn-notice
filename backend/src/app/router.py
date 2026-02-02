from fastapi import APIRouter

from src.app.chat.router import router as chat_router
from src.app.projects.router import router as projects_router
from src.app.sections.router import router as sections_router
from src.app.tasks.router import router as tasks_router
from src.app.todos.router import router as todos_router

# Create the root API router
api_router = APIRouter()

# Include domain routers
api_router.include_router(todos_router, prefix='/todos', tags=['todos'])
api_router.include_router(chat_router, prefix='/chat', tags=['chat'])
api_router.include_router(projects_router, prefix='/projects', tags=['projects'])
api_router.include_router(sections_router, prefix='/sections', tags=['sections'])
api_router.include_router(tasks_router, prefix='/tasks', tags=['tasks'])
