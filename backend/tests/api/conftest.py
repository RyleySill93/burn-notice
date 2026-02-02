from contextlib import contextmanager
from typing import Callable, Dict

import pytest
from fastapi.testclient import TestClient
from starlette.middleware import Middleware

from src.core.authentication import (
    AuthenticatedUser,
    AuthenticationService,
    authenticate_user,
)
from src.core.authorization import AuthorizationService
from src.core.authorization.guards import _authorize_staff_member, _authorize_user


@pytest.fixture(autouse=True)
def patch_isolated_session(monkeypatch):
    """
    Patch IsolatedSession to use PatchedIsolatedSession for all API tests.

    -    This ensures that isolated transactions in code (like updating last_used_at)
    -    don't create truly isolated sessions that can't see test data.
    """
    from src.network.database.session import PatchedIsolatedSession

    # Patch the IsolatedSession class directly in the database.session module
    monkeypatch.setattr('src.network.database.session.IsolatedSession', PatchedIsolatedSession)


@contextmanager
def _make_persistent_client(dependency_overrides: Dict[Callable, Callable] | None = None):
    """
    Helper to create a persistent TestClient with optional dependency overrides.

    Removes HTTPSessionManagerMiddleware so multiple requests share state.
    Optionally applies dependency overrides for authentication/authorization.

    Args:
        dependency_overrides: Dict mapping dependency functions to override functions

    Yields:
        TestClient with persistence and overrides applied
    """
    from src.network.database.middleware import HTTPSessionManagerMiddleware
    from src.network.http.server import server

    @contextmanager
    def _temporary_remove_middleware(target_name: str):
        """
        Temporarily remove middleware and restore it after use
        We use this to mimic a persistent client
        """
        # Store original middleware state
        original_middleware = server.user_middleware.copy()

        # Remove from server
        new_middlewares: list[Middleware] = []
        for middleware in server.user_middleware:
            if not middleware.cls.__name__ == target_name:
                new_middlewares.append(middleware)
        server.user_middleware = new_middlewares
        server.middleware_stack = server.build_middleware_stack()

        try:
            yield server
        finally:
            # Restore original middleware state
            server.user_middleware = original_middleware
            server.middleware_stack = server.build_middleware_stack()

    # Apply dependency overrides if provided
    if dependency_overrides:
        for dependency, override in dependency_overrides.items():
            server.dependency_overrides[dependency] = override

    try:
        with _temporary_remove_middleware(HTTPSessionManagerMiddleware.__name__) as modified_server:
            with TestClient(modified_server) as client:
                yield client
    finally:
        # Clean up dependency overrides
        if dependency_overrides:
            for dependency in dependency_overrides:
                server.dependency_overrides.pop(dependency, None)


@pytest.fixture(scope='module')
def client() -> TestClient:
    from src.network.http.server import server

    with TestClient(server) as c:
        yield c


@pytest.fixture(scope='function')
def persistent_client() -> TestClient:
    """
    TestClient that persists data between HTTP requests within a single test.

    Removes HTTPSessionManagerMiddleware so multiple requests share state,
    useful for testing multi-step flows (e.g., MFA setup -> verify -> login).

    Note: Data persists between requests within the test, but is cleaned up
    after the test completes (function scope).
    """
    with _make_persistent_client() as client:
        yield client


@pytest.fixture(scope='function')
def staff_client(staff_user) -> TestClient:
    """
    Get a client authenticated as a staff user
    """
    from src.network.http.server import server

    def authorize_staff_user():
        authz_service = AuthorizationService.factory()
        return authz_service.get_auth_user_from_id(staff_user.id)

    server.dependency_overrides[_authorize_staff_member] = authorize_staff_user
    server.dependency_overrides[_authorize_user] = authorize_staff_user
    with TestClient(server) as c:
        yield c

    # clear Dependency
    server.dependency_overrides.pop(_authorize_user)
    server.dependency_overrides.pop(_authorize_staff_member)


@pytest.fixture(scope='function')
def customer_admin_client(customer_admin_user) -> TestClient:
    """
    Get a client authenticated as a customer admin user
    """
    from src.network.http.server import server

    def _authenticate_customer_admin_user():
        authn_service = AuthenticationService.factory()
        token = authn_service.create_auth_token(user_id=customer_admin_user.id, ip_address='127.0.0.1')
        access_token_contents = authn_service.verify_jwt_token(token.access_token)
        return AuthenticatedUser(
            id=customer_admin_user.id,
            impersonator_id=None,
            token=access_token_contents,
        )

    server.dependency_overrides[authenticate_user] = _authenticate_customer_admin_user
    with TestClient(server) as c:
        yield c

    # clear Dependency
    server.dependency_overrides.pop(authenticate_user)


@pytest.fixture(scope='function')
def persistent_staff_client(staff_user) -> TestClient:
    """
    Persistent client authenticated as a staff user.

    Combines persistent session behavior with staff authentication.
    Data persists between requests within the test.
    """

    def authorize_staff_user():
        authz_service = AuthorizationService.factory()
        return authz_service.get_auth_user_from_id(staff_user.id)

    overrides = {
        _authorize_staff_member: authorize_staff_user,
        _authorize_user: authorize_staff_user,
    }

    with _make_persistent_client(dependency_overrides=overrides) as client:
        yield client


@pytest.fixture(scope='function')
def persistent_customer_admin_client(customer_admin_user) -> TestClient:
    """
    Persistent client authenticated as a customer admin user.

    Combines persistent session behavior with customer admin authentication.
    Data persists between requests within the test.
    """

    def _authenticate_customer_admin_user():
        authn_service = AuthenticationService.factory()
        token = authn_service.create_auth_token(user_id=customer_admin_user.id, ip_address='127.0.0.1')
        access_token_contents = authn_service.verify_jwt_token(token.access_token)
        return AuthenticatedUser(
            id=customer_admin_user.id,
            impersonator_id=None,
            token=access_token_contents,
        )

    overrides = {authenticate_user: _authenticate_customer_admin_user}

    with _make_persistent_client(dependency_overrides=overrides) as client:
        yield client
