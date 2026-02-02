from typing import List, Set

from src.app.projects.domains import ProjectCreate, ProjectRead, ProjectUpdate
from src.app.projects.models import Project
from src.common.nanoid import NanoIdType
from src.network.database.repository.exceptions import RepositoryObjectNotFound


class ProjectNotFound(Exception):
    """Raised when a project is not found"""

    pass


class ProjectService:
    @classmethod
    def factory(cls) -> 'ProjectService':
        return cls()

    def list_projects_for_customer_id(self, customer_id: NanoIdType) -> List[ProjectRead]:
        """List all projects for a customer"""
        return Project.list(Project.customer_id == customer_id)

    def list_projects_for_customer_id_and_project_ids(
        self,
        customer_id: NanoIdType,
        project_ids: Set[NanoIdType],
    ) -> List[ProjectRead]:
        """List projects for a customer filtered by permitted project IDs"""
        if not project_ids:
            return []
        return Project.list(
            Project.customer_id == customer_id,
            Project.id.in_(project_ids),
        )

    def list_projects_for_customer_ids(self, customer_ids: Set[NanoIdType]) -> List[ProjectRead]:
        """List all projects for a set of customer IDs"""
        if not customer_ids:
            return []
        return Project.list(Project.customer_id.in_(customer_ids))

    def get_project_for_id(self, project_id: NanoIdType) -> ProjectRead:
        """Get a project by ID, raises ProjectNotFound if not found"""
        try:
            return Project.get(Project.id == project_id)
        except RepositoryObjectNotFound:
            raise ProjectNotFound(f'Project with id {project_id} not found')

    def get_project_for_id_or_none(self, project_id: NanoIdType) -> ProjectRead | None:
        """Get a project by ID, returns None if not found"""
        try:
            return Project.get(Project.id == project_id)
        except RepositoryObjectNotFound:
            return None

    def create_project(self, project: ProjectCreate) -> ProjectRead:
        """Create a new project"""
        return Project.create(project)

    def update_project(self, project_id: NanoIdType, project: ProjectUpdate) -> ProjectRead:
        """Update a project"""
        self.get_project_for_id(project_id)

        updates = project.model_dump(exclude_unset=True)
        if updates:
            return Project.update(project_id, **updates)
        return self.get_project_for_id(project_id)

    def delete_project(self, project_id: NanoIdType) -> None:
        """Delete a project"""
        self.get_project_for_id(project_id)
        Project.delete(Project.id == project_id)

    def get_all_project_ids(self) -> Set[NanoIdType]:
        """Get all project IDs in the system"""
        return {p.id for p in Project.list()}

    def get_project_ids_for_customer_ids(self, customer_ids: Set[NanoIdType]) -> Set[NanoIdType]:
        """Get all project IDs for a set of customer IDs"""
        if not customer_ids:
            return set()
        return {p.id for p in Project.list(Project.customer_id.in_(customer_ids))}
