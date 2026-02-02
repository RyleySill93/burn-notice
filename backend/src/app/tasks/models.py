from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.tasks.constants import TASK_PK_ABBREV
from src.app.tasks.domains import TaskCreate, TaskRead
from src.common.model import BaseModel


class Task(BaseModel[TaskRead, TaskCreate]):
    __pk_abbrev__ = TASK_PK_ABBREV
    __create_domain__ = TaskCreate
    __read_domain__ = TaskRead

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('project.id'), nullable=False)
    section_id: Mapped[Optional[str]] = mapped_column(ForeignKey('section.id'), nullable=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(ForeignKey('task.id'), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship('Project')
    section = relationship('Section')
    parent_task = relationship('Task', remote_side='Task.id', foreign_keys=[parent_task_id])
