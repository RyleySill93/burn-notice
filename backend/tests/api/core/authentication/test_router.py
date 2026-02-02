from fastapi.testclient import TestClient

from src import settings
from src.core.user import AuthenticatedUserRead


def test_login_with_email_challenge(client: TestClient, staff_user: AuthenticatedUserRead) -> None:
    """
    Test that an email challenge can be generated via login
    """
    login_data = {
        'email': staff_user.email,
    }
    response = client.post(
        f'{settings.API_PREFIX}/auth/generate-email-challenge',
        json=login_data,
    )
    assert response.status_code == 201
