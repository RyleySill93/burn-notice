import decimal

from fastapi import APIRouter, status
from fastapi.testclient import TestClient

from src.common.exceptions import APIException, InternalException
from src.network.http.server import server

api_test_router = APIRouter()


@api_test_router.get('/common/exception/api')
def get_api_exception():
    message = "Ouch i'm in conflict!"
    raise APIException(message=message, code=status.HTTP_409_CONFLICT)


@api_test_router.get('/common/exception/internal')
def get_internal_exception():
    """
    Retrieve items.
    """

    class BadException(InternalException): ...

    raise BadException(context={'broken': 'test'})


@api_test_router.get('/common/exception/validation')
def get_pydantic_exception(some_decimal: decimal.Decimal):
    """
    Retrieve items.
    """
    return


server.include_router(api_test_router, prefix='/test')


def test_inbound_validation_exception_handler(
    client: TestClient,
) -> None:
    response = client.get('/test/common/exception/validation', params={'some_decimal': 'nvm'})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    content = response.json()
    # {'detail': [{'loc': ['query', 'some_decimal'], 'message': 'Input should be a valid decimal', 'input': 'nvm, 'type': 'decimal_parsing'}]}
    assert content['detail'][0]['input'] == 'nvm'
    assert content['detail'][0]['message'] == 'Input should be a valid decimal'


def test_api_exception_handler(
    client: TestClient,
) -> None:
    response = client.get(
        '/test/common/exception/api',
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    content = response.json()
    assert content['detail'] == "Ouch i'm in conflict!"


def test_internal_exception_handler(
    client: TestClient,
) -> None:
    response = client.get(
        '/test/common/exception/internal',
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    content = response.json()
    assert content['detail'] == InternalException.default_detail
