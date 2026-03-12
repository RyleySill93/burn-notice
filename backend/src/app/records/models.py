from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.records.constants import RECORD_PK_ABBREV
from src.app.records.domains import RecordCreate, RecordRead
from src.common.model import BaseModel


class Record(BaseModel[RecordRead, RecordCreate]):
    """Tracks personal and company records for tokens and time burned."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id'), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)  # tokens, time
    record_period: Mapped[str] = mapped_column(String(20), nullable=False)  # daily, weekly, monthly
    record_scope: Mapped[str] = mapped_column(String(20), nullable=False)  # personal, company
    value: Mapped[float] = mapped_column(Float, nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)

    engineer = relationship('Engineer')
    customer = relationship('Customer')

    __pk_abbrev__ = RECORD_PK_ABBREV
    __read_domain__ = RecordRead
    __create_domain__ = RecordCreate

    __table_args__ = (
        Index('idx_record_engineer_type_period', 'engineer_id', 'record_type', 'record_period'),
        Index('idx_record_customer_type_period', 'customer_id', 'record_type', 'record_period'),
        Index('idx_record_scope', 'record_scope'),
        Index('idx_record_date', 'record_date'),
    )
