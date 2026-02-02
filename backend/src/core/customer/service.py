from typing import List

from src.common.nanoid import NanoIdType
from src.core.customer.domains import CustomerRead
from src.core.customer.models import Customer


class CustomerService:
    @classmethod
    def factory(cls) -> 'CustomerService':
        return cls()

    def list_customers_for_ids(self, customer_ids: List[NanoIdType]) -> List[CustomerRead]:
        """List customers by their IDs"""
        return Customer.list(Customer.id.in_(customer_ids))

    def get_for_id(self, customer_id: NanoIdType) -> CustomerRead:
        """Get a customer by ID"""
        return Customer.get(Customer.id == customer_id)
