import datetime

from pydantic import EmailStr, computed_field, model_validator

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType


class AuthenticatedUserRead(BaseDomain):
    id: NanoIdType
    email: str
    is_active: bool = False
    hashed_password: str | None = None
    archived_at: datetime.datetime | None = None


class UserRead(BaseDomain):
    id: NanoIdType
    first_name: str | None = None
    last_name: str | None = None
    email: str
    is_active: bool = False
    hashed_password: str | None = None
    archived_at: datetime.datetime | None = None

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}"


class UserUpdate(BaseDomain):
    first_name: str | None = None
    last_name: str | None = None
    hashed_password: str | None = None

    @model_validator(mode='after')
    def return_type_validator(self):
        self.first_name = self.first_name.strip() if self.first_name else None
        self.last_name = self.last_name.strip() if self.last_name else None
        return self


class UserCreate(UserUpdate):
    email: EmailStr
