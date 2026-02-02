from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.common.model import BaseModel
from src.core.customer.constants import CUSTOMER_PK_ABBREV
from src.core.customer.domains import CustomerCreate, CustomerRead


class Customer(BaseModel[CustomerRead, CustomerCreate]):
    name: Mapped[str] = mapped_column(String, nullable=False)

    __pk_abbrev__ = CUSTOMER_PK_ABBREV
    __read_domain__ = CustomerRead
    __create_domain__ = CustomerCreate
