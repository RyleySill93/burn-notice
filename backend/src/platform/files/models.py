import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.common.model import BaseModel
from src.platform.files.domains import FileCreate, FileRead


class File(BaseModel[FileRead, FileCreate]):
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    file_name: Mapped[str] = mapped_column(String(length=1000))
    size: Mapped[int] = mapped_column(BigInteger, nullable=True, comment='File size in bytes')
    s3_key: Mapped[Optional[str]] = mapped_column(String(length=1000))
    is_public: Mapped[bool] = mapped_column(Boolean(), default=False)
    # needodo - handling user deletion
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __read_domain__ = FileRead
    __create_domain__ = FileCreate
    __system_audit__ = True
