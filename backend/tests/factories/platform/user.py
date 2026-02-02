from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from src.core.user import UserCreate
from tests.factories.base import Faker


@register_fixture(scope='session', autouse=True, name='user_factory')
class UserFactory(ModelFactory[UserCreate]):
    __model__ = UserCreate

    phone = Faker.phone_number
    hashed_password = lambda: 'password'
