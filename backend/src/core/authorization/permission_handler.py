from abc import ABC, abstractmethod
from typing import List, Optional, Set

from src.common.nanoid import NanoIdType
from src.core.authorization.constants import PermissionEffectEnum, PermissionTypeEnum, ResourceTypeEnum
from src.core.authorization.domains import AccessPolicyRead


class PermissionHandler(ABC):
    """
    Abstract base class for resource-specific permission handling.

    This class defines the interface that all resource permission handlers must implement.
    Each resource type (e.g., Customer, Project, etc.) should have its own handler that
    implements the resource-specific permission logic.

    By using this pattern, the PermissionService can delegate resource-specific
    permission checks to the appropriate handler without having direct knowledge of
    each resource type's implementation details, following the Open/Closed Principle.

    Handlers are organized in a hierarchical schema where parent handlers pass down
    their permitted resource IDs to child handlers. For example:
    - CustomerPermissionHandler receives membership customer_ids and returns permitted customer_ids
    - ProjectPermissionHandler receives those customer_ids and returns permitted project_ids
    - TaskPermissionHandler receives those project_ids and returns permitted task_ids
    """

    @property
    @abstractmethod
    def resource_type(self) -> ResourceTypeEnum:
        """
        Return the resource type this handler is responsible for.

        Returns:
            The ResourceTypeEnum value for this handler
        """
        pass

    @abstractmethod
    def get_all_resource_ids(self) -> Set[NanoIdType]:
        """
        Get all resource IDs of this type in the system.

        This is primarily used for staff access where they have access to all resources.

        Returns:
            A set of all resource IDs of this type
        """
        pass

    @abstractmethod
    def get_universe(
        self,
        parent_resource_ids: Set[NanoIdType],
    ) -> Set[NanoIdType]:
        """
        Get the universe of resources accessible given the parent resource IDs.

        This defines what resources a user could potentially access based on their
        access to parent resources, before applying specific permission rules.

        For root-level handlers (e.g., Customer), parent_resource_ids would be the
        customer IDs from the user's memberships. For child handlers, it would be
        the permitted IDs returned by the parent handler.

        Args:
            parent_resource_ids: Set of parent resource IDs the user has access to.

        Returns:
            A set of resource IDs that are in the user's accessible universe
        """
        pass

    @abstractmethod
    def get_hierarchical_resource_ids(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        parent_resource_ids: Optional[Set[NanoIdType]] = None,
    ) -> Set[NanoIdType]:
        """
        Get resource IDs through hierarchical permission inheritance.

        Some resources inherit permissions from parent resources (e.g., a project
        might inherit permissions from its customer). This method returns the
        resource IDs that are accessible through such hierarchical inheritance.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            parent_resource_ids: Set of parent resource IDs the user has access to

        Returns:
            A set of resource IDs accessible through hierarchical inheritance
        """
        pass

    def filter_by_permission_model(
        self,
        candidate_ids: Set[NanoIdType],
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
    ) -> Set[NanoIdType]:
        """
        Filter candidate resource IDs based on the full permission model.

        This method takes a set of candidate resource IDs and filters them
        based on explicit ALLOW/DENY rules.

        Args:
            candidate_ids: Set of resource IDs that might be accessible
            rules: List of permission rules to apply
            permission_type: The type of permission being checked

        Returns:
            A set of resource IDs that pass all permission checks
        """
        if not candidate_ids:
            return set()

        permitted_ids = set()

        # Build sets of explicit allow/deny for this resource type
        explicit_allow_ids = set()
        explicit_deny_ids = set()

        for rule in rules:
            if rule.permission_type == permission_type and rule.resource_type == self.resource_type:
                resource_ids = self.extract_resource_ids_from_rule(rule)
                if rule.effect == PermissionEffectEnum.ALLOW:
                    explicit_allow_ids.update(resource_ids)
                else:  # DENY
                    explicit_deny_ids.update(resource_ids)

        # Check each candidate against the rules
        for resource_id in candidate_ids:
            if resource_id in explicit_deny_ids:
                continue
            if resource_id in explicit_allow_ids or resource_id in candidate_ids:
                permitted_ids.add(resource_id)

        return permitted_ids

    def has_hierarchical_permission(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        resource_id: NanoIdType,
    ) -> bool:
        """
        Check if a user has permission to a specific resource through hierarchy.

        This method first checks for explicit DENY/ALLOW rules at the resource level,
        then delegates to the resource-specific hierarchical check.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            resource_id: The specific resource ID to check

        Returns:
            True if the user has hierarchical permission, False otherwise
        """
        # First check for any DENY rules at this resource level
        if self.has_matching_deny_rule(rules, permission_type, resource_id):
            return False

        # Check for ALLOW rules at this resource level
        if self.has_matching_allow_rule(rules, permission_type, resource_id):
            return True

        # Delegate to resource-specific hierarchical check
        return self._has_hierarchical_permission(rules, permission_type, resource_id)

    @abstractmethod
    def _has_hierarchical_permission(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        resource_id: NanoIdType,
    ) -> bool:
        """
        Resource-specific hierarchical permission check.

        This method is called after explicit DENY/ALLOW rules have been checked.
        Implementations should check for inherited permissions from parent resources.

        For root-level handlers (e.g., Customer), this should return False since
        there is no parent to inherit from.

        For child handlers (e.g., Project), this should check if the parent resource
        (e.g., Customer) has a permission that grants access to this resource.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            resource_id: The specific resource ID to check

        Returns:
            True if the user has inherited permission, False otherwise
        """
        pass

    @abstractmethod
    def list_resources_for_customer(self, customer_id: NanoIdType) -> List[dict]:
        """
        List all resources of this type for a specific customer.

        This is used for UI purposes to show available resources that can be
        used in policy resource selectors.

        Args:
            customer_id: The customer ID to list resources for

        Returns:
            List of dictionaries with 'id' and 'name' keys for each resource
        """
        pass

    def extract_resource_ids_from_rule(self, rule: AccessPolicyRead) -> Set[NanoIdType]:
        """
        Extract resource IDs from a permission rule's resource selector.

        This is a helper method that can be used by implementations to extract
        the actual resource IDs from different selector types.

        Args:
            rule: The permission rule to extract IDs from

        Returns:
            A set of resource IDs specified by the rule's selector
        """
        from src.core.authorization.constants import ResourceSelectorTypeEnum

        selector_type = rule.resource_selector.get('type')

        if selector_type == ResourceSelectorTypeEnum.EXACT:
            resource_id = rule.resource_selector.get('id')
            return {resource_id} if resource_id else set()

        elif selector_type == ResourceSelectorTypeEnum.MULTIPLE:
            return set(rule.resource_selector.get('ids', []))

        elif selector_type == ResourceSelectorTypeEnum.WILDCARD:
            return set()

        elif selector_type == ResourceSelectorTypeEnum.WILDCARD_EXCEPT:
            return set()

        return set()

    def has_matching_allow_rule(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        resource_id: NanoIdType = None,
    ) -> bool:
        """
        Check if any rule explicitly grants permission to the resource.

        Args:
            rules: List of permission rules to check
            permission_type: The type of permission being requested
            resource_id: The ID of the specific resource being accessed

        Returns:
            True if a matching ALLOW rule is found, False otherwise
        """
        for rule in rules:
            if (
                rule.permission_type == permission_type
                and rule.resource_type == self.resource_type
                and rule.effect == PermissionEffectEnum.ALLOW
            ):
                if self._selector_matches_resource(rule.resource_selector, resource_id):
                    return True
        return False

    def has_matching_deny_rule(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        resource_id: NanoIdType = None,
    ) -> bool:
        """
        Check if any rule explicitly denies permission to the resource.

        Args:
            rules: List of permission rules to check
            permission_type: The type of permission being requested
            resource_id: The ID of the specific resource being accessed

        Returns:
            True if a matching DENY rule is found, False otherwise
        """
        for rule in rules:
            if (
                rule.permission_type == permission_type
                and rule.resource_type == self.resource_type
                and rule.effect == PermissionEffectEnum.DENY
            ):
                if self._selector_matches_resource(rule.resource_selector, resource_id):
                    return True
        return False

    def _selector_matches_resource(self, selector: dict, resource_id: NanoIdType = None) -> bool:
        """
        Determine if a resource selector matches a specific resource.

        Args:
            selector: The selector definition from the permission rule
            resource_id: The ID of the specific resource being checked

        Returns:
            True if the selector matches the resource, False otherwise
        """
        from src.core.authorization.constants import ResourceSelectorTypeEnum

        selector_type = selector.get('type')

        if not resource_id:
            return selector_type in (ResourceSelectorTypeEnum.WILDCARD, ResourceSelectorTypeEnum.WILDCARD_EXCEPT)

        if selector_type == ResourceSelectorTypeEnum.WILDCARD:
            return True

        if selector_type == ResourceSelectorTypeEnum.WILDCARD_EXCEPT:
            excluded_ids = selector.get('excluded_ids', [])
            return resource_id not in excluded_ids

        if selector_type == ResourceSelectorTypeEnum.EXACT:
            return selector.get('id') == resource_id

        if selector_type == ResourceSelectorTypeEnum.MULTIPLE:
            return resource_id in selector.get('ids', [])

        return False
