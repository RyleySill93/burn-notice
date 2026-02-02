from typing import List, Optional, Set

from src.common.nanoid import NanoIdType
from src.core.authorization.constants import PermissionEffectEnum, PermissionTypeEnum, ResourceTypeEnum
from src.core.authorization.domains import AccessPolicyRead
from src.core.authorization.permission_handler import PermissionHandler
from src.core.customer.models import Customer
from src.core.customer.service import CustomerService


class CustomerPermissionHandler(PermissionHandler):
    """
    Permission handler for Customer resource access.

    This handler implements the permission checking logic for Customer resources,
    which are the root of the permission hierarchy. Users access customers through
    their memberships, and this handler determines which customers a user can access
    based on their membership customer IDs and permission rules.
    """

    def __init__(self, customer_service: CustomerService = None):
        self._customer_service = customer_service

    @property
    def customer_service(self) -> CustomerService:
        if self._customer_service is None:
            self._customer_service = CustomerService.factory()
        return self._customer_service

    @property
    def resource_type(self) -> ResourceTypeEnum:
        return ResourceTypeEnum.CUSTOMER

    def get_all_resource_ids(self) -> Set[NanoIdType]:
        """
        Get all customer IDs in the system.

        This is primarily used for staff access where they have access to all customers.

        Returns:
            A set of all customer IDs
        """
        return {c.id for c in Customer.list()}

    def get_universe(
        self,
        parent_resource_ids: Set[NanoIdType],
    ) -> Set[NanoIdType]:
        """
        Get the universe of customers accessible given the membership customer IDs.

        For this handler (root of the hierarchy), parent_resource_ids are the
        customer IDs from the user's memberships. The universe is simply those
        same customer IDs since memberships define which customers a user belongs to.

        Args:
            parent_resource_ids: Set of customer IDs from the user's memberships

        Returns:
            A set of customer IDs in the user's accessible universe
        """
        return parent_resource_ids if parent_resource_ids else set()

    def get_hierarchical_resource_ids(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        parent_resource_ids: Optional[Set[NanoIdType]] = None,
    ) -> Set[NanoIdType]:
        """
        Get customer IDs through hierarchical permission inheritance.

        Collects customer IDs from rules that grant permission at the customer level.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            parent_resource_ids: Not used for this handler (root of hierarchy)

        Returns:
            A set of customer IDs accessible through hierarchical inheritance
        """
        customer_ids = set()

        for rule in rules:
            if (
                rule.permission_type == permission_type
                and rule.resource_type == ResourceTypeEnum.CUSTOMER
                and rule.effect == PermissionEffectEnum.ALLOW
            ):
                customer_ids.update(self.extract_resource_ids_from_rule(rule))

        return customer_ids

    def _has_hierarchical_permission(
        self,
        rules: List[AccessPolicyRead],
        permission_type: PermissionTypeEnum,
        resource_id: NanoIdType,
    ) -> bool:
        """
        Check for inherited permissions from parent resources.

        For customers (root of hierarchy), there is no parent to inherit from,
        so this always returns False.

        Args:
            rules: List of permission rules to evaluate
            permission_type: The type of permission being checked
            resource_id: The customer ID to check

        Returns:
            Always False for customers (no parent hierarchy)
        """
        return False

    def list_resources_for_customer(self, customer_id: NanoIdType) -> List[dict]:
        """
        List all customers for the given customer ID.

        For customer resources, we only return the current customer since
        customers don't "belong" to other customers.

        Args:
            customer_id: The customer ID to list resources for

        Returns:
            List with a single dictionary containing the customer's id and name
        """
        customer = self.customer_service.get_for_id(customer_id=customer_id)
        return [{'id': customer.id, 'name': customer.name}]
