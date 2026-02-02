from typing import List

from src.common.nanoid import NanoIdType
from src.core.authentication.constants import AuthenticationMethodEnum
from src.core.authentication.domains import CustomerAuthSettingsCreate, CustomerAuthSettingsRead
from src.core.authentication.models import CustomerAuthSettings


class CustomerAuthSettingsService:
    @classmethod
    def factory(cls) -> 'CustomerAuthSettingsService':
        return cls()

    def get(self, customer_id: NanoIdType) -> CustomerAuthSettingsRead:
        return CustomerAuthSettings.get(customer_id=customer_id)

    def create_default_customer_auth_settings(self, customer_id: NanoIdType):
        default_setting = CustomerAuthSettingsCreate(
            customer_id=customer_id,
            enabled_auth_methods=[AuthenticationMethodEnum.PASSWORD.value, AuthenticationMethodEnum.MAGIC_LINK.value],
        )
        CustomerAuthSettings.create(default_setting)

    def list_customer_auth_settings(self, customer_ids: List[NanoIdType]) -> List[CustomerAuthSettingsRead]:
        return CustomerAuthSettings.list(CustomerAuthSettings.customer_id.in_(customer_ids))
