from fastapi import APIRouter
from pydantic import BaseModel

from src.app.engineers.domains import EngineerRead
from src.app.engineers.service import EngineerService

router = APIRouter()


class EngineerCreateRequest(BaseModel):
    external_id: str
    display_name: str


@router.post('', response_model=EngineerRead)
def create_or_update_engineer(request: EngineerCreateRequest) -> EngineerRead:
    """Register or update an engineer."""
    return EngineerService.get_or_create(
        external_id=request.external_id,
        display_name=request.display_name,
    )


@router.get('', response_model=list[EngineerRead])
def list_engineers() -> list[EngineerRead]:
    """List all engineers."""
    return EngineerService.list_all()


@router.get('/{external_id}', response_model=EngineerRead | None)
def get_engineer(external_id: str) -> EngineerRead | None:
    """Get an engineer by external ID."""
    return EngineerService.get_by_external_id(external_id)
