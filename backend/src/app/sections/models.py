from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.sections.constants import SECTION_PK_ABBREV
from src.app.sections.domains import SectionCreate, SectionRead
from src.common.model import BaseModel


class Section(BaseModel[SectionRead, SectionCreate]):
    __pk_abbrev__ = SECTION_PK_ABBREV
    __create_domain__ = SectionCreate
    __read_domain__ = SectionRead

    name: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey('project.id'), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship('Project')
