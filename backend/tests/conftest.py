import os
import sys
from typing import Any

from sqlalchemy.orm import Session

# from tests.factories.base import Faker

# Test Environment Overrides will override .env files
# THESE MUST BE IMPORTED BEFORE ANYTHING
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load the special .env file into the OS environment
EXPECTED_SECRET_KEY = 'test'
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('ENVIRONMENT', 'testing')
os.environ.setdefault('COMPANY_NAME', 'TestCompany')
os.environ.setdefault('VITE_COMPANY_NAME', 'Test Company, Inc.')
os.environ.setdefault('VITE_SUPPORT_EMAIL', 'support@testcompany.com')
os.environ.setdefault('VITE_COMPANY_WEBSITE', 'www.testcompany.com')
os.environ.setdefault('VITE_LOGO_URL', 'https://test.com/logo.png')
os.environ.setdefault('EMAIL_FROM_ADDRESS', 'noreply@testcompany.com')
os.environ.setdefault('AWS_STORAGE_BUCKET_NAME', 'test-bucket')
os.environ.setdefault('DB_NAME', 'test-db')
os.environ.setdefault('DB_USER', 'burn_notice')
os.environ.setdefault('DB_ENCRYPTION_KEY', 'test-encryption-key')
os.environ.setdefault('DB_ENCRYPTION_SALT', 'test-salt')
os.environ.setdefault('ATOMIC_REQUESTS', 'False')
os.environ.setdefault('USE_MOCK_WEBSOCKETS', 'True')
os.environ.setdefault('USE_MOCK_DRAMATIQ_BROKER', 'True')
os.environ.setdefault('USE_MOCK_SENTRY_CLIENT', 'True')
os.environ.setdefault('USE_MOCK_EMAIL_CLIENT', 'True')
os.environ.setdefault('USE_MOCK_SMS_CLIENT', 'True')
os.environ.setdefault('USE_MOCK_FILE_CLIENT', 'True')
os.environ.setdefault('USE_MOCK_SLACK_CLIENT', 'True')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import setup

setup.run()

# Import models to ensure they're registered
from src.common.model import import_model_modules

# Import all model modules to register them with SQLAlchemy
import_model_modules()

from unittest import mock

import pytest

from src.common import context
from src.core.user import UserService

# Add fixtures here
pytest_plugins = [
    'tests.factories.platform.user',
    'tests.factories.core.customer',
]

# ruff: noqa: E402
from src import settings

# TODO: Entity models and services don't exist - tests need to be rewritten
# from src.core.entity.domain import EntityCreate, EntityRelationshipCreate, PeriodTypeCreate, TrackedPeriodTypeCreate
# from src.core.customer.models import Customer, Entity, EntityRelationship
# from src.core.entity.services.entity_service import EntityService
from src.core.authorization import (
    STAFF_ROLE_NAME,
    AccessControlService,
    AccessRole,
    AccessRoleCreate,
)
from src.core.customer import Customer
from src.core.membership import Membership, MembershipCreate
from src.network.database.session import db as session_manager
from src.platform.email.client import EmailClientDomain

# TODO: Remove namespace references - no longer used
# Legacy namespace constants kept temporarily for reference
# ENTITY_NAMESPACE_DEFAULT = 'ENTITY'
# CLUSTER_NAMESPACE_DEFAULT = 'CLUSTER'


# When src files are imported before the above patching, tests will use
# incorrect database settings as well as non mocked services.
if settings.SECRET_KEY != EXPECTED_SECRET_KEY:
    print(settings.SECRET_KEY, EXPECTED_SECRET_KEY)
    raise ValueError(
        'Patching of environment variables failed.\n'
        'This will cause unexpected test failures'
        'Check all src imports are delayed until after patching.\n'
    )


@pytest.fixture(autouse=True)
def mock_boto3_session(monkeypatch):
    """
    Ensure no files make it to S3
    """
    with mock.patch('boto3.session.Session') as mock_session:
        yield mock_session


@pytest.fixture(scope='function', autouse=True)
def db() -> Session:
    # This needs to be set first for fixtures to be able to create
    context.initialize(
        user_type=context.AppContextUserType.SYSTEM.value,
        user_id='user-system',
        breadcrumb='testing',
    )

    with session_manager(commit_on_success=False):
        session = session_manager.session

        # Patch commit() to prevent accidental commits in tests
        # This allows production code to use db.session.commit() naturally
        # without breaking test rollbacks
        def no_op_commit():
            # In tests, flush changes but don't actually commit
            # This makes the changes visible within the transaction
            # but keeps them rollbackable
            session.flush()

        session.commit = no_op_commit

        yield session_manager.session

    session.rollback()


@pytest.fixture(scope='function')
def caught_emails(monkeypatch) -> list[EmailClientDomain]:
    """
    Fixture that returns any sent emails during the function calls
    def sample_test(use_email_catcher):
        service.something_that_sends_an_email_as_side_effect()
        caught_emails = use_email_catcher
        assert len(caught_emails) == 1
    """
    caught_email_container = []
    monkeypatch.setattr(
        'src.platform.email.client.MockEmailClient.get_email_catcher', lambda self: caught_email_container
    )

    # Emails sent through the Email.send method can route through a broker
    # Ensure that doesn't happen for the email to be successfully caught
    def _always_sync_send(
        self,
        send_kwargs: dict[str, Any],
        send_on_commit: bool = True,
        send_async: bool = True,
    ):
        from src.platform.email.tasks import _send_template_email

        # Mirrors Email._send but calls synchronously regardless
        _send_template_email(**send_kwargs)

    monkeypatch.setattr('src.platform.email.email.Email._send', _always_sync_send)
    return caught_email_container


@pytest.fixture(scope='function')
def staff_user(user_factory):
    """
    Create a user that can be granted staff access.

    Note: This fixture just creates the user. Tests that need the user to have
    staff access should call AccessControlService.factory().grant_staff_admin_access()
    after creating a membership for the user.
    """
    staff_user = user_factory.build(email='staff-user@burn_notice.com')
    iservice = UserService.factory()
    user = iservice.create_user(staff_user)

    # Ensure the Staff role exists
    role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
    if not role:
        AccessRole.create(AccessRoleCreate(name=STAFF_ROLE_NAME, description='Staff role for system administrators'))

    return user


@pytest.fixture(scope='function')
def non_staff_user(user_factory):
    non_staff_user = user_factory.build(email='user@burn_notice.com')
    iservice = UserService.factory()
    user = iservice.create_user(non_staff_user)
    return user


@pytest.fixture(scope='function')
def customer(customer_factory):
    """
    Creates a test customer.
    """

    customer_data = customer_factory.build()
    return Customer.create(customer_data)


@pytest.fixture(scope='function')
def customer_admin_user(user_factory, customer):
    """
    Creates a user with admin permissions for the given customer.
    Similar to entity_admin_user in poliwrath.
    """
    import uuid

    # Create a unique user for customer admin with a UUID to avoid email collisions
    unique_id = str(uuid.uuid4())[:8]
    customer_admin = user_factory.build(email=f'customer-admin-{unique_id}@burn_notice.com')
    user_service = UserService.factory()
    user = user_service.create_user(customer_admin)

    # Create membership for the user and customer
    membership = Membership.create(MembershipCreate(user_id=user.id, customer_id=customer.id, is_active=True))

    # Grant customer admin access
    AccessControlService.factory().grant_customer_admin_access(
        membership_id=membership.id, customer_id=customer.id, customer_name=customer.name
    )

    return user
