from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.app.todos.constants import TODO_PK_ABBREV
from src.app.todos.domains import TodoCreate, TodoRead
from src.common.model import BaseModel


class Todo(BaseModel[TodoRead, TodoCreate]):
    __pk_abbrev__ = TODO_PK_ABBREV
    __create_domain__ = TodoCreate
    __read_domain__ = TodoRead

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
