from src.common.nanoid import NanoIdType
from src.core.authentication import AuthenticationService
from src.core.authorization import AccessControlService, PermissionService
from src.core.authorization.constants import STAFF_ROLE_NAME
from src.core.authorization.domains import Me, MembershipAssignmentCreate, MyLoginConfig
from src.core.authorization.models import AccessRole, MembershipAssignment
from src.core.customer import Customer, CustomerCreate, CustomerService
from src.core.membership import Membership, MembershipCreate, MembershipService
from src.core.user import UserCreate, UserNotFound, UserRead, UserService


class CoreService:
    """
    Service for cross-domain operations that span multiple services.

    This service handles operations that require coordination between
    multiple domain services, such as creating a customer with an admin
    membership or creating staff users across all customers.
    """

    def __init__(
        self,
        permission_service: PermissionService,
        access_control_service: AccessControlService,
        authentication_service: AuthenticationService,
        membership_service: MembershipService,
        customer_service: CustomerService,
        user_service: UserService,
    ):
        self.permission_service = permission_service
        self.access_control_service = access_control_service
        self.authentication_service = authentication_service
        self.membership_service = membership_service
        self.customer_service = customer_service
        self.user_service = user_service

    @classmethod
    def factory(cls) -> 'CoreService':
        return cls(
            permission_service=PermissionService.factory(),
            access_control_service=AccessControlService.factory(),
            authentication_service=AuthenticationService.factory(),
            membership_service=MembershipService.factory(),
            customer_service=CustomerService.factory(),
            user_service=UserService.factory(),
        )

    def get_me(self, user_id: NanoIdType, impersonator_id: NanoIdType | None = None) -> Me:
        """
        Get comprehensive user profile information including memberships and permissions.

        This method builds a complete user profile with all relevant information needed
        for the frontend, including:
        - Basic user details
        - All memberships with associated customers
        - Permission scopes
        - Impersonation information if applicable

        Args:
            user_id: The ID of the user to get information for
            impersonator_id: Optional ID of a user who is impersonating this user

        Returns:
            A Me object containing the user's complete profile
        """
        user = self.user_service.get_user_for_id(user_id=user_id)
        memberships = self.membership_service.list_memberships_with_customers_for_user(user_id=user_id)
        # Enrich customer data if needed
        for membership in memberships:
            if membership.customer:
                # Get full customer object to access additional attributes like logo_url
                full_customer = self.customer_service.get_for_id(membership.customer.id)
                if full_customer and hasattr(full_customer, 'logo_url'):
                    # Add logo as a custom attribute
                    membership.customer.customer_logo = full_customer.logo_url

        impersonator_email = None
        impersonator_full_name = None
        if impersonator_id:
            impersonator_user = self.user_service.get_user_for_id(user_id=impersonator_id)
            impersonator_email = impersonator_user.email
            impersonator_full_name = impersonator_user.full_name

        return Me(
            id=user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            impersonator_id=impersonator_id,
            impersonator_email=impersonator_email,
            impersonator_full_name=impersonator_full_name,
            scopes=None,
            memberships=memberships,
            is_staff=self.permission_service.is_staff_user_id(user_id=user_id),
            is_super_staff=self.permission_service.is_super_staff_user_id(user_id=user_id),
        )

    def create_staff_user(self, email: str, first_name: str, last_name: str) -> UserRead:
        """
        Creates staff user memberships for all customers and assigns the staff role.

        This method performs the following operations in bulk:
        1. Creates memberships for all customers for the given user
        2. Assigns the staff role to all those memberships

        Args:
            email: The email of the user to make a staff user
            first_name: The first name of the user
            last_name: The last name of the user

        Returns:
            The created user

        Raises:
            ValueError: If the staff role doesn't exist
        """
        user_create = UserCreate(email=email, first_name=first_name, last_name=last_name)
        # Create new user
        user, _ = self.user_service.get_or_create_user(user_create)
        # First, get the Staff role ID
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        if not staff_role:
            raise ValueError(f"Staff role '{STAFF_ROLE_NAME}' not found in the system.")

        # Get all customers
        customers = Customer.list()

        # delete all assignments for memberships then delete the memberships
        memberships = Membership.list(Membership.user_id == user.id)
        MembershipAssignment.delete(MembershipAssignment.membership_id.in_([m.id for m in memberships]))
        Membership.delete(Membership.user_id == user.id)
        # Create memberships in bulk for all customers
        memberships_to_create = [
            MembershipCreate(
                user_id=user.id,
                customer_id=customer.id,
                is_active=True,  # Staff memberships are active immediately
            )
            for customer in customers
        ]

        # Bulk create memberships
        Membership.bulk_create(memberships_to_create)
        created_memberships = Membership.list(Membership.user_id == user.id)
        # Prepare assignments in bulk
        assignments_to_create = [
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=staff_role.id)
            for membership in created_memberships
        ]

        # Bulk create assignments
        MembershipAssignment.bulk_create(assignments_to_create)

        # Invalidate permission cache for the user
        self.permission_service.invalidate_permission_cache(user.id)

        return user

    def create_customer_with_admin_membership(self, user_id: NanoIdType, name: str) -> Me:
        """
        Create a new customer and assign the user as admin.

        This method is used when a user without any memberships creates their first customer.
        It performs the following operations:
        1. Creates a new Customer with the given name
        2. Creates a Membership linking the user to the customer
        3. Grants the user admin access to the customer

        Args:
            user_id: The ID of the user creating the customer
            name: The name of the customer to create

        Returns:
            The updated Me object with the new membership
        """
        # Create the customer
        customer = Customer.create(CustomerCreate(name=name))

        # Create membership for the user
        membership = self.membership_service.create_customer_membership(
            user_id=user_id,
            customer_id=customer.id,
        )

        # Grant admin access
        self.access_control_service.grant_customer_admin_access(
            membership_id=membership.id,
            customer_id=customer.id,
            customer_name=name,
        )

        # Return updated Me object
        return self.get_me(user_id=user_id)

    def get_my_login_config_for_email(self, email: str, raise_exceptions: bool = True) -> MyLoginConfig:
        """
        Retrieve login configuration settings for a user based on their email.

        This method is called by edge routes to fetch the required login settings for an email address.
        It handles security by returning default login settings for invalid emails to avoid
        leaking information about registered users.

        Args:
            email: The email address to get login configuration for
            raise_exceptions: Whether to raise exceptions for invalid emails

        Returns:
            A MyLoginConfig object with appropriate login settings
        """
        user = None
        try:
            user = self.user_service.get_user_for_email(email)
        except UserNotFound:
            if raise_exceptions:
                raise

        if not user:
            return MyLoginConfig.for_anonymous_user(email=email)

        # Determine who user has access to
        memberships = self.membership_service.list_memberships_for_user(user_id=user.id)
        customer_ids = [membership.customer_id for membership in memberships if membership.customer_id]
        if not customer_ids:
            # User has no memberships - this is a weird case but we dont want to throw
            return MyLoginConfig.for_anonymous_user(email=email)

        # Get the strongest auth settings
        user_auth_settings = self.authentication_service.get_customer_auth_settings(
            user_id=user.id, customer_ids=customer_ids
        )
        return MyLoginConfig(email=email, has_password=bool(user.hashed_password), auth_settings=user_auth_settings)
