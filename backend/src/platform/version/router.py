from fastapi import APIRouter
from starlette.responses import JSONResponse

router = APIRouter()


@router.get('/api')
def get_app_version() -> JSONResponse:
    """Get the current application version"""
    from src.version import VERSION

    return JSONResponse({'version': VERSION})
