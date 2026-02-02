from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.engineers.domains import EngineerCreate, EngineerRead
from src.common.model import BaseModel


class Engineer(BaseModel[EngineerRead, EngineerCreate]):
    """An engineer being tracked for token usage."""

    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id'), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    customer = relationship('Customer')

    __pk_abbrev__ = 'eng'
    __read_domain__ = EngineerRead
    __create_domain__ = EngineerCreate

    __table_args__ = (
        # external_id is unique per customer (team)
        Index('idx_engineer_customer_external', 'customer_id', 'external_id', unique=True),
    )
