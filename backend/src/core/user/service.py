import datetime

from sqlalchemy import func

from src.common.nanoid import NanoIdType

# TODO: Entity module doesn't exist - using membership module instead
from src.core.membership import Membership
from src.core.membership import MembershipRead as UserWithMembership
from src.core.user.domains import AuthenticatedUserRead, UserCreate, UserRead, UserUpdate
from src.core.user.exceptions import UserNotFound
from src.core.user.models import User
from src.network.database.repository.exceptions import RepositoryObjectNotFound


class UserService:
    @classmethod
    def factory(cls) -> 'UserService':
        return cls()

    def get_user_for_id(self, user_id: NanoIdType) -> UserRead:
        try:
            return User.get(id=user_id)
        except RepositoryObjectNotFound:
            raise UserNotFound(message=f'User not found with id: {user_id}')

    def get_user_with_membership_for_id(self, user_id: NanoIdType, customer_id: NanoIdType) -> UserWithMembership:
        user = User.get(id=user_id)
        # Note: get_with_entities method doesn't exist on Membership
        membership = Membership.get(
            user_id=user.id,
            customer_id=customer_id,
        )

        # UserWithMembership.from_user_and_membership doesn't exist
        # Just return the membership for now
        return membership

    def create_user(self, user: UserCreate) -> UserRead:
        return User.create(user)

    def get_or_create_user(self, user_create: UserCreate) -> tuple[UserRead, bool]:
        existing_user = User.get_or_none(func.lower(User.email) == func.lower(user_create.email))

        if existing_user:
            return existing_user, False

        return User.create(
            UserCreate(
                email=user_create.email,
                first_name=user_create.first_name,
                last_name=user_create.last_name,
            )
        ), True

    def list_users_for_ids(self, user_ids: list[NanoIdType]) -> list[UserRead]:
        return User.list(User.id.in_(user_ids))

    def get_user_for_email(self, email: str) -> UserRead:
        try:
            return User.get(func.lower(User.email) == func.lower(email))
        except RepositoryObjectNotFound:
            raise UserNotFound(message=f'User not found with email: {email}')

    def get_user_for_email_or_none(self, email: str) -> UserRead | None:
        return User.get_or_none(func.lower(User.email) == func.lower(email))

    def search_users(self, search: str) -> list[UserRead]:
        return User.search(search)

    def update_user(self, id: NanoIdType, user_update: UserUpdate):
        User.update(id=id, **user_update.to_dict())

    def activate_user(self, user_id: NanoIdType):
        User.update(id=user_id, is_active=True)

    def archive_user(self, user_id: NanoIdType):
        archived_at = datetime.datetime.now()
        User.update(id=user_id, archived_at=archived_at)

    def get_auth_user_for_email(self, email: str) -> AuthenticatedUserRead:
        try:
            return User.get_auth_user(func.lower(User.email) == func.lower(email))
        except RepositoryObjectNotFound:
            raise UserNotFound(message=f'User not found with email: {email}')
