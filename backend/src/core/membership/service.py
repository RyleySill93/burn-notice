from typing import List

from src.common.nanoid import NanoIdType
from src.core.membership.domains import MembershipCreate, MembershipRead, MembershipWithCustomer, MembershipWithUser
from src.core.membership.models import Membership


class MembershipService:
    @classmethod
    def factory(cls) -> 'MembershipService':
        return cls()

    def list_memberships_for_user(self, user_id: NanoIdType) -> List[MembershipRead]:
        """List all memberships for a specific user"""
        return Membership.list(Membership.user_id == user_id)

    def list_memberships_for_customer(self, customer_id: NanoIdType) -> List[MembershipRead]:
        """List all memberships for a specific customer"""
        return Membership.list(Membership.customer_id == customer_id)

    def list_memberships_with_customers_for_user(self, user_id: NanoIdType) -> List['MembershipWithCustomer']:
        """List memberships with related customer data for a user"""
        from src.core.customer import CustomerService

        memberships = self.list_memberships_for_user(user_id)
        result = []
        customer_service = CustomerService.factory()

        for membership in memberships:
            membership_with_customer = MembershipWithCustomer(**membership.model_dump(), customer=None)
            if membership.customer_id:
                customer = customer_service.get_for_id(membership.customer_id)
                if customer:
                    membership_with_customer.customer = customer
            result.append(membership_with_customer)

        return result

    def list_membership_customers_for_user_by_email(self, email: str) -> List[NanoIdType]:
        """Get list of customer IDs for a user by email"""
        from src.core.user import UserService

        user = UserService.factory().get_user_for_email_or_none(email)
        if not user:
            return []

        memberships = self.list_memberships_for_user(user.id)
        return [m.customer_id for m in memberships if m.customer_id]

    def get_membership_for_id(self, membership_id: NanoIdType) -> MembershipRead:
        """Get a single membership by ID"""
        return Membership.get(id=membership_id)

    def create_customer_membership(self, user_id: NanoIdType, customer_id: NanoIdType) -> MembershipRead:
        """Create a new membership linking a user to a customer"""
        membership_data = MembershipCreate(customer_id=customer_id, user_id=user_id, is_active=True)
        return Membership.create(membership_data)

    def list_memberships_with_users_for_customer(self, customer_id: NanoIdType) -> List[MembershipWithUser]:
        """List memberships with related user data for a customer (team members)"""
        from src.core.user import UserService

        memberships = self.list_memberships_for_customer(customer_id)
        result = []
        user_service = UserService.factory()

        for membership in memberships:
            membership_with_user = MembershipWithUser(**membership.model_dump(), user=None)
            if membership.user_id:
                user = user_service.get_user_for_id(membership.user_id)
                if user:
                    membership_with_user.user = user
            result.append(membership_with_user)

        return result

    def get_membership_for_id_or_none(self, membership_id: NanoIdType) -> MembershipRead | None:
        """Get a single membership by ID, or None if not found"""
        return Membership.get_or_none(Membership.id == membership_id)

    def delete_membership(self, membership_id: NanoIdType) -> None:
        """Delete a membership and its associated role assignments"""
        from src.core.authorization.models import MembershipAssignment

        # Delete any role assignments for this membership first
        MembershipAssignment.delete(MembershipAssignment.membership_id == membership_id)

        # Delete the membership itself
        Membership.delete(Membership.id == membership_id)
