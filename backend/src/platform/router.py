from fastapi import APIRouter

from src.core.authentication import router as authentication
from src.core.authorization.router import authorization_router
from src.core.invitation.router import router as invitation_router
from src.platform.files import router as files
from src.platform.healthcheck import router as healthcheck
from src.platform.version import router as version

api_router = APIRouter()
api_router.include_router(healthcheck.router, prefix='/healthcheck', tags=['healthcheck'])
api_router.include_router(version.router, prefix='/version', tags=['version'])
api_router.include_router(authentication.router, prefix='/auth', tags=['auth'])
api_router.include_router(authorization_router, prefix='/authorization', tags=['authorization'])
api_router.include_router(invitation_router, prefix='/invitations', tags=['invitations'])
api_router.include_router(files.router, prefix='/files', tags=['files'])
