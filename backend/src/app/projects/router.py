from typing import Dict, List

from fastapi import APIRouter, Depends, status

from src.app.projects import ProjectNotFound, ProjectService
from src.app.projects.domains import ProjectCreate, ProjectRead, ProjectUpdate
from src.common.exceptions import APIException
from src.common.nanoid import NanoIdType
from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import AuthenticatedUserGuard
from src.core.authorization import PermissionService
from src.core.authorization.constants import PermissionTypeEnum, ResourceTypeEnum

router = APIRouter()


@router.get('/list-projects')
def list_projects(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_service: PermissionService = Depends(PermissionService.factory),
    project_service: ProjectService = Depends(ProjectService.factory),
) -> List[ProjectRead]:
    """List projects for a customer that user has access to"""
    # Get the set of project IDs the user has READ permission for
    permitted_project_ids = permission_service.list_permitted_ids(
        user_id=user.id,
        permission_type=PermissionTypeEnum.READ,
        resource_type=ResourceTypeEnum.PROJECT,
    )

    # Filter to projects in the requested customer
    return project_service.list_projects_for_customer_id_and_project_ids(
        customer_id=customer_id,
        project_ids=permitted_project_ids,
    )


@router.get('/get-project/{project_id}')
def get_project(
    project_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_service: PermissionService = Depends(PermissionService.factory),
    project_service: ProjectService = Depends(ProjectService.factory),
) -> ProjectRead:
    """Get a project by ID (requires READ permission)"""
    try:
        project = project_service.get_project_for_id(project_id)
    except ProjectNotFound:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message='Project not found')

    has_permission = permission_service.check_permission(
        user_id=user.id,
        permission_type=PermissionTypeEnum.READ,
        resource_type=ResourceTypeEnum.PROJECT,
        resource_id=project_id,
    )

    if not has_permission:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Permission denied')

    return project


@router.post('/create-project')
def create_project(
    payload: ProjectCreate,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_service: PermissionService = Depends(PermissionService.factory),
    project_service: ProjectService = Depends(ProjectService.factory),
) -> ProjectRead:
    """Create a new project (requires admin permission on customer)"""
    has_permission = permission_service.check_permission(
        user_id=user.id,
        permission_type=PermissionTypeEnum.ADMIN,
        resource_type=ResourceTypeEnum.CUSTOMER,
        resource_id=payload.customer_id,
    )

    if not has_permission:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Only team admins can create projects',
        )

    payload.user_id = user.id  # Set creator
    project = project_service.create_project(payload)

    # Invalidate permission cache for all customer members so they can see the new project
    permission_service.invalidate_customer_member_user_cache(payload.customer_id)

    return project


@router.patch('/update-project/{project_id}')
def update_project(
    project_id: NanoIdType,
    payload: ProjectUpdate,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_service: PermissionService = Depends(PermissionService.factory),
    project_service: ProjectService = Depends(ProjectService.factory),
) -> ProjectRead:
    """Update a project (requires WRITE permission)"""
    try:
        project_service.get_project_for_id(project_id)
    except ProjectNotFound:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message='Project not found')

    has_permission = permission_service.check_permission(
        user_id=user.id,
        permission_type=PermissionTypeEnum.WRITE,
        resource_type=ResourceTypeEnum.PROJECT,
        resource_id=project_id,
    )

    if not has_permission:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Permission denied')

    return project_service.update_project(project_id, payload)


@router.delete('/delete-project/{project_id}')
def delete_project(
    project_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_service: PermissionService = Depends(PermissionService.factory),
    project_service: ProjectService = Depends(ProjectService.factory),
) -> Dict[str, str]:
    """Delete a project (requires admin permission on customer)"""
    try:
        project = project_service.get_project_for_id(project_id)
    except ProjectNotFound:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message='Project not found')

    has_permission = permission_service.check_permission(
        user_id=user.id,
        permission_type=PermissionTypeEnum.ADMIN,
        resource_type=ResourceTypeEnum.CUSTOMER,
        resource_id=project.customer_id,
    )

    if not has_permission:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Only team admins can delete projects',
        )

    project_service.delete_project(project_id)
    return {'message': 'Project deleted successfully'}
