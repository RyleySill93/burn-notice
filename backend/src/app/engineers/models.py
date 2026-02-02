from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.app.engineers.domains import EngineerCreate, EngineerRead
from src.common.model import BaseModel


class Engineer(BaseModel[EngineerRead, EngineerCreate]):
    """An engineer being tracked for token usage."""

    external_id: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    __pk_abbrev__ = 'eng'
    __read_domain__ = EngineerRead
    __create_domain__ = EngineerCreate
