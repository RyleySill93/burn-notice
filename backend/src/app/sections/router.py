from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.app.projects.models import Project
from src.app.sections.domains import SectionCreate, SectionRead, SectionUpdate
from src.app.sections.models import Section
from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import AuthenticatedUserGuard
from src.network.database.repository.exceptions import RepositoryObjectNotFound

router = APIRouter()


@router.get('/list-sections')
def list_sections(
    project_id: Optional[str] = None,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> List[SectionRead]:
    if project_id:
        # Verify user owns the project
        try:
            Project.get(Project.id == project_id, Project.user_id == user.id)
        except RepositoryObjectNotFound:
            raise HTTPException(status_code=404, detail='Project not found')
        return Section.list(Section.project_id == project_id)

    # Get all sections for user's projects
    user_projects = Project.list(Project.user_id == user.id)
    project_ids = [p.id for p in user_projects]
    if not project_ids:
        return []
    return Section.list(Section.project_id.in_(project_ids))


@router.get('/get-section/{section_id}')
def get_section(
    section_id: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> SectionRead:
    try:
        section = Section.get(Section.id == section_id)
        # Verify user owns the project
        Project.get(Project.id == section.project_id, Project.user_id == user.id)
        return section
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Section not found')


@router.post('/create-section')
def create_section(
    section: SectionCreate,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> SectionRead:
    # Verify user owns the project
    try:
        Project.get(Project.id == section.project_id, Project.user_id == user.id)
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Project not found')
    return Section.create(section)


@router.patch('/update-section/{section_id}')
def update_section(
    section_id: str,
    section: SectionUpdate,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> SectionRead:
    try:
        existing_section = Section.get(Section.id == section_id)
        # Verify user owns the project
        Project.get(Project.id == existing_section.project_id, Project.user_id == user.id)
        updates = section.model_dump(exclude_unset=True)
        if updates:
            return Section.update(section_id, **updates)
        return existing_section
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Section not found')


@router.delete('/delete-section/{section_id}')
def delete_section(
    section_id: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> Dict[str, str]:
    try:
        section = Section.get(Section.id == section_id)
        # Verify user owns the project
        Project.get(Project.id == section.project_id, Project.user_id == user.id)
        Section.delete(Section.id == section_id)
        return {'message': 'Section deleted successfully'}
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Section not found')
