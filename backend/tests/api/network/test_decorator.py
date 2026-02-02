from fastapi import APIRouter, status
from fastapi.testclient import TestClient

from src.common.exceptions import APIException
from src.network.database.decorator import read_only_route
from src.network.http.server import server

api_test_router = APIRouter()


@api_test_router.get('/not-read-only')
def does_not_use_read_only_route():
    from src.network.database.session import db

    is_read_only = getattr(db.session, '_is_read_only', False)
    if is_read_only:
        raise APIException(message='Not using the read only!', code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return


@read_only_route
@api_test_router.get('/read-only')
def uses_read_only_route():
    from src.network.database.session import db

    is_read_only = getattr(db.session, '_is_read_only', False)
    if not is_read_only:
        raise APIException(message='Not using the read only!', code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return


server.include_router(api_test_router, prefix='/test/network')


def test_decorator_uses_read_only_route(
    client: TestClient,
) -> None:
    """
    If this test passes, it means the session manager would have went for the read only database
    """
    response = client.get('/test/network/read-only')
    print(response.json())
    assert response.status_code == status.HTTP_200_OK


def test_not_decorated_uses_read_write_route(
    client: TestClient,
) -> None:
    """
    If this test passes, it means the session manager would have went for the read only database
    """
    response = client.get('/test/network/not-read-only')
    print(response.json())
    assert response.status_code == status.HTTP_200_OK
