from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.common.nanoid import NanoId, NanoIdType

ENGINEER_PK_ABBREV = 'eng'


class EngineerCreate(BaseModel):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=ENGINEER_PK_ABBREV))
    customer_id: str  # Team/customer ID
    external_id: str  # e.g., "alice@company.com" or "alice-macbook"
    display_name: str

    def to_dict(self) -> dict:
        return self.model_dump()


class EngineerRead(BaseModel):
    id: str
    customer_id: str
    external_id: str
    display_name: str
    created_at: datetime
    modified_at: datetime | None = None

    model_config = {'from_attributes': True}
