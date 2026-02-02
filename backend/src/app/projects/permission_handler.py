from typing import List, Optional, Set

from src.app.projects.service import ProjectService
from src.common.nanoid import NanoIdType
from src.core.authorization.constants import (
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.domains import AccessPolicyRead
from src.core.authorization.permission_handler import PermissionHandler


class ProjectPermissionHandler(PermissionHandler):
    """
    Permission handler for Project resource access.

    This handler implements the permission checking logic for Project resources.
    Projects belong to customers, so permission inheritance flows from customers
    to projects. Users with customer-level permissions automatically have access
    to projects within that customer.
    """

    def __init__(self, project_service: ProjectService = None):
        self._project_service = project_service

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService.factory()
        return self._project_service

    @property
    def resource_type(self) -> ResourceTypeEnum:
        return ResourceTypeEnum.PROJECT

    def get_all_resource_ids(self) -> Set[NanoIdType]:
        """
        Get all project IDs in the system.

        This is primarily used for staff access where they have access to all projects.

        Returns:
            A set of all project IDs
        """
        return self.project_service.get_all_project_ids()

    def get_universe(
        self,
        parent_resource_ids: Set[NanoIdType],
    ) -> Set[NanoIdType]:
        """
        Get the universe of projects accessible given the parent customer IDs.

        For projects, parent_resource_ids are the customer IDs the user has access to.
        The universe includes all projects that belong to those customers.

        Args:
            parent_resource_ids: Set of customer IDs the user has access to

        Returns:
            A set of project IDs in the user's accessible universe
        """
        return self.project_service.get_project_ids_for_customer_ids(parent_resource_ids)

    def get_hierarchical_resource_ids(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        parent_resource_ids: Optional[Set[NanoIdType]] = None,
    ) -> Set[NanoIdType]:
        """
        Get project IDs through hierarchical permission inheritance.

        Projects inherit permissions from their parent customers. If a user has
        permission at the customer level, they automatically have access to all
        projects within that customer.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            parent_resource_ids: Set of customer IDs with permission (optional, will be computed from rules if not provided)

        Returns:
            A set of project IDs accessible through hierarchical inheritance
        """
        project_ids = set()

        # Get projects from explicit project-level ALLOW rules
        for rule in rules:
            if (
                rule.permission_type == permission_type
                and rule.resource_type == ResourceTypeEnum.PROJECT
                and rule.effect == PermissionEffectEnum.ALLOW
            ):
                project_ids.update(self.extract_resource_ids_from_rule(rule))

        # Get customer IDs from customer-level ALLOW rules if not provided
        # Check for all permission types that imply the requested permission
        # (ADMIN implies WRITE implies READ)
        if parent_resource_ids is None:
            parent_resource_ids = set()
            if permission_type == PermissionTypeEnum.READ:
                implied_types = [PermissionTypeEnum.READ, PermissionTypeEnum.WRITE, PermissionTypeEnum.ADMIN]
            elif permission_type == PermissionTypeEnum.WRITE:
                implied_types = [PermissionTypeEnum.WRITE, PermissionTypeEnum.ADMIN]
            else:
                implied_types = [PermissionTypeEnum.ADMIN]

            for rule in rules:
                if (
                    rule.permission_type in implied_types
                    and rule.resource_type == ResourceTypeEnum.CUSTOMER
                    and rule.effect == PermissionEffectEnum.ALLOW
                ):
                    parent_resource_ids.update(self.extract_resource_ids_from_rule(rule))

        # Get projects from customer-level permission inheritance
        if parent_resource_ids:
            customer_projects = self.project_service.get_project_ids_for_customer_ids(parent_resource_ids)
            project_ids.update(customer_projects)

        return project_ids

    def _has_hierarchical_permission(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        resource_id: NanoIdType,
    ) -> bool:
        """
        Check for inherited permissions from parent customer.

        This checks if the project's parent customer has a permission rule
        that grants access to this project.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            resource_id: The project ID to check

        Returns:
            True if the user has inherited permission from customer, False otherwise
        """
        project = self.project_service.get_project_for_id_or_none(resource_id)
        if not project:
            return False

        # Check if there's a customer-level permission that grants access
        for rule in rules:
            if (
                rule.permission_type == permission_type
                and rule.resource_type == ResourceTypeEnum.CUSTOMER
                and rule.effect == PermissionEffectEnum.ALLOW
            ):
                if self._selector_matches_resource(rule.resource_selector, project.customer_id):
                    return True

        return False

    def list_resources_for_customer(self, customer_id: NanoIdType) -> List[dict]:
        """
        List all projects for the given customer.

        Args:
            customer_id: The customer ID to list projects for

        Returns:
            List of dictionaries with 'id' and 'name' keys for each project
        """
        projects = self.project_service.list_projects_for_customer_id(customer_id)
        return [{'id': p.id, 'name': p.name} for p in projects]
