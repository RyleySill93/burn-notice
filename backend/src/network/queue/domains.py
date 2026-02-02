import hashlib
import hmac
from enum import Enum
from typing import Any
from uuid import UUID

from src import settings
from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType


class JobStatusEnum(str, Enum):
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'


class JobStatusDomain(BaseDomain):
    job_id: UUID
    status: JobStatusEnum
    id: NanoIdType | None = None
    message: str | None = None


class SignedMessageKey(BaseDomain):
    message_key: str
    signature_hex: str  # HMAC-SHA256 of task_id and secret key

    @classmethod
    def get_signature(cls, message_key: str) -> bytes:
        return hmac.new(settings.DRAMATIQ_SECRET_KEY.encode(), message_key.encode(), hashlib.sha256).digest()

    @classmethod
    def sign_message(cls, message_key: str) -> 'SignedMessageKey':
        signature = cls.get_signature(message_key)
        return cls(message_key=message_key, signature_hex=signature.hex())

    def __str__(self) -> str:
        return f'{self.message_key}_{self.signature_hex}'

    @classmethod
    def read(cls, string: str) -> 'SignedMessageKey':
        message_key, signature_hex = string.split('_')
        # Generate a new signature with the secret key and compare
        expected_signature = cls.get_signature(message_key)
        if not hmac.compare_digest(signature_hex, expected_signature.hex()):
            raise ValueError('Invalid signature')
        return cls(message_key=message_key, signature_hex=signature_hex)


class TaskResultDomain(BaseDomain):
    status: JobStatusDomain
    result: Any | None = None


class SignedMessageKeyDomain(BaseDomain):
    signed_message_key: str
