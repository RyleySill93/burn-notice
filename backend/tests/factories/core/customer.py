from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from src.core.customer import CustomerCreate
from tests.factories.base import Faker


@register_fixture(scope='session', autouse=True, name='customer_factory')
class CustomerFactory(ModelFactory[CustomerCreate]):
    __model__ = CustomerCreate

    name = Faker.company
