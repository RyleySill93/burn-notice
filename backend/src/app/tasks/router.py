from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.app.projects.models import Project
from src.app.tasks.domains import TaskCreate, TaskRead, TaskUpdate
from src.app.tasks.models import Task
from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import AuthenticatedUserGuard
from src.network.database.repository.exceptions import RepositoryObjectNotFound

router = APIRouter()


@router.get('/list-tasks')
def list_tasks(
    project_id: Optional[str] = None,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> List[TaskRead]:
    if project_id:
        # Verify user owns the project
        try:
            Project.get(Project.id == project_id, Project.user_id == user.id)
        except RepositoryObjectNotFound:
            raise HTTPException(status_code=404, detail='Project not found')
        return Task.list(Task.project_id == project_id)

    # Get all tasks for user's projects
    user_projects = Project.list(Project.user_id == user.id)
    project_ids = [p.id for p in user_projects]
    if not project_ids:
        return []
    return Task.list(Task.project_id.in_(project_ids))


@router.get('/get-task/{task_id}')
def get_task(
    task_id: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> TaskRead:
    try:
        task = Task.get(Task.id == task_id)
        # Verify user owns the project
        Project.get(Project.id == task.project_id, Project.user_id == user.id)
        return task
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Task not found')


@router.post('/create-task')
def create_task(
    task: TaskCreate,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> TaskRead:
    # Verify user owns the project
    try:
        Project.get(Project.id == task.project_id, Project.user_id == user.id)
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Project not found')
    return Task.create(task)


@router.patch('/update-task/{task_id}')
def update_task(
    task_id: str,
    task: TaskUpdate,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> TaskRead:
    try:
        existing_task = Task.get(Task.id == task_id)
        # Verify user owns the project
        Project.get(Project.id == existing_task.project_id, Project.user_id == user.id)
        updates = task.model_dump(exclude_unset=True)
        if updates:
            return Task.update(task_id, **updates)
        return existing_task
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Task not found')


@router.delete('/delete-task/{task_id}')
def delete_task(
    task_id: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> Dict[str, str]:
    try:
        task = Task.get(Task.id == task_id)
        # Verify user owns the project
        Project.get(Project.id == task.project_id, Project.user_id == user.id)
        Task.delete(Task.id == task_id)
        return {'message': 'Task deleted successfully'}
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Task not found')
