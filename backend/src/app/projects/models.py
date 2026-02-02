from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.projects.constants import PROJECT_PK_ABBREV
from src.app.projects.domains import ProjectCreate, ProjectRead
from src.common.model import BaseModel


class Project(BaseModel[ProjectRead, ProjectCreate]):
    __pk_abbrev__ = PROJECT_PK_ABBREV
    __create_domain__ = ProjectCreate
    __read_domain__ = ProjectRead

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    customer = relationship('Customer')
    user = relationship('User')
