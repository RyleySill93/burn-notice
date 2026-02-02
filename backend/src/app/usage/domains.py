from datetime import date, datetime

from pydantic import BaseModel


class UsageCreate(BaseModel):
    engineer_id: str
    tokens_input: int = 0
    tokens_output: int = 0
    model: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict:
        return self.model_dump()


class UsageRead(BaseModel):
    id: str
    engineer_id: str
    tokens_input: int
    tokens_output: int
    model: str | None
    session_id: str | None
    created_at: datetime

    model_config = {'from_attributes': True}

    @property
    def total_tokens(self) -> int:
        return self.tokens_input + self.tokens_output


class UsageDailyCreate(BaseModel):
    engineer_id: str
    date: date
    total_tokens: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    session_count: int = 0

    def to_dict(self) -> dict:
        return self.model_dump()


class UsageDailyRead(BaseModel):
    id: str
    engineer_id: str
    date: date
    total_tokens: int
    tokens_input: int
    tokens_output: int
    session_count: int
    created_at: datetime

    model_config = {'from_attributes': True}
