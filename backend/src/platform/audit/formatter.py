import abc
from typing import Any

from src.common.nanoid import NanoIdType
from src.core.entity.services.entity_service import EntityService
from src.core.user import User, UserRead
from src.platform.audit.domain import AuditLogRead


class AuditFormatter(abc.ABC):
    def __init__(self, entity_service=None):
        self.entity_service = entity_service

    @classmethod
    def factory(cls):
        return cls(entity_service=EntityService.factory())

    @abc.abstractmethod
    def format(self, audit_logs: list[AuditLogRead]) -> list[Any]: ...

    def _filter_original(self, original: dict) -> dict:
        return {key: value for key, value in original.items() if key not in self.EXCLUDED_KEYS}

    def _filter_changed(self, changes: dict | None) -> dict:
        if not changes:
            return {}
        return {key: value for key, value in changes.items() if key not in self.EXCLUDED_KEYS}

    def _filter_empty_changes(self, audit_logs: list[dict]) -> dict:
        """
        Always send insert and delete but exclude update if there are no relevant changes
        """
        return [
            audit_log
            for audit_log in audit_logs
            if audit_log.operation_type != 'UPDATE' or audit_log.operation_type == 'UPDATE' and audit_log.changed_data
        ]

    def _get_user_for_id(self, user_ids: list[NanoIdType]) -> dict[NanoIdType, UserRead]:
        users = User.list(User.id.in_(user_ids))
        return {user.id: user for user in users}

    def _get_entity_name_by_id(self, entity_ids: list[NanoIdType]) -> dict[NanoIdType, str]:
        entities = self.entity_service.list_for_ids(entity_ids=entity_ids)
        return {entity.id: entity.name for entity in entities}
