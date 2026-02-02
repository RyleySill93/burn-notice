from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.usage.domains import UsageCreate, UsageDailyCreate, UsageDailyRead, UsageRead
from src.common.model import BaseModel


class Usage(BaseModel[UsageRead, UsageCreate]):
    """Raw token usage event."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    engineer = relationship('Engineer')

    __pk_abbrev__ = 'usg'
    __read_domain__ = UsageRead
    __create_domain__ = UsageCreate

    __table_args__ = (Index('idx_usage_engineer_created', 'engineer_id', 'created_at'),)


class UsageDaily(BaseModel[UsageDailyRead, UsageDailyCreate]):
    """Pre-aggregated daily usage totals."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_input: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_output: Mapped[int] = mapped_column(BigInteger, default=0)
    session_count: Mapped[int] = mapped_column(Integer, default=0)

    engineer = relationship('Engineer')

    __pk_abbrev__ = 'usgd'
    __read_domain__ = UsageDailyRead
    __create_domain__ = UsageDailyCreate

    __table_args__ = (
        Index('idx_usage_daily_engineer_date', 'engineer_id', 'date', unique=True),
        Index('idx_usage_daily_date', 'date'),
    )
