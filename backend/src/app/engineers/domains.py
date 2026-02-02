from datetime import datetime

from pydantic import BaseModel


class EngineerCreate(BaseModel):
    external_id: str  # e.g., "alice@company.com" or "alice-macbook"
    display_name: str

    def to_dict(self) -> dict:
        return self.model_dump()


class EngineerRead(BaseModel):
    id: str
    external_id: str
    display_name: str
    created_at: datetime
    modified_at: datetime | None = None

    model_config = {'from_attributes': True}
