import enum
from typing import Any


class BaseEnum(str, enum.Enum):
    @classmethod
    def has(cls, item: Any) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def list_all(cls) -> list[str]:
        return [e.value for e in cls]
