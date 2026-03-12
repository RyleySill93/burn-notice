from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.medals.constants import MEDAL_PK_ABBREV
from src.app.medals.domains import MedalCreate, MedalRead
from src.common.model import BaseModel


class Medal(BaseModel[MedalRead, MedalCreate]):
    """Tracks medals awarded to engineers for rankings and milestones."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id'), nullable=False, index=True)
    medal_category: Mapped[str] = mapped_column(String(20), nullable=False)  # ranking, milestone
    medal_type: Mapped[str] = mapped_column(String(20), nullable=False)  # gold, silver, bronze, token_10m, etc.
    metric_type: Mapped[str] = mapped_column(String(20), nullable=False)  # tokens, time
    period_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # weekly, monthly
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    awarded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey('user.id'), nullable=True)

    engineer = relationship('Engineer')
    customer = relationship('Customer')
    awarded_by_user = relationship('User', foreign_keys=[awarded_by_user_id])

    __pk_abbrev__ = MEDAL_PK_ABBREV
    __read_domain__ = MedalRead
    __create_domain__ = MedalCreate

    __table_args__ = (
        Index('idx_medal_engineer_category', 'engineer_id', 'medal_category'),
        Index('idx_medal_customer_category', 'customer_id', 'medal_category'),
        Index('idx_medal_period', 'customer_id', 'period_type', 'period_start'),
    )
