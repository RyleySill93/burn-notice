from datetime import datetime
from importlib import import_module
from typing import Any, Optional, Type

from loguru import logger
from sqlalchemy import DateTime, String, func, text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src import settings
from src.common.nanoid import NanoId, NanoIdType
from src.network.database.repository.mixin import (
    BaseQueryManager,
    CreateDomainType,
    CurrentVersionManager,
    ReadDomainType,
    RepositoryMixin,
)


class BaseModel(DeclarativeBase, RepositoryMixin[ReadDomainType, CreateDomainType]):
    __pk_abbrev__: str = NotImplemented

    @declared_attr
    def id(cls) -> Mapped[str]:
        # Ensure an abbreviation is implemented
        if cls.__pk_abbrev__ == NotImplemented:
            raise NotImplementedError(f'__pk_abbrev__ must be implemented for {cls.__name__}')

        return mapped_column(
            String(length=50), primary_key=True, server_default=text(f"gen_nanoid('{cls.__pk_abbrev__}')")
        )

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(DateTime, server_default=func.now())

    @declared_attr
    def modified_at(cls) -> Mapped[Optional[datetime]]:
        return mapped_column(DateTime, onupdate=func.now(), nullable=True)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    @declared_attr.directive
    def __system_audit__(cls) -> bool:
        return False

    @declared_attr.directive
    def __app_audit__(cls) -> bool:
        return False

    @declared_attr.directive
    def __app_audit_context_builder__(cls) -> str:
        return NotImplemented

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(id={self.id!r})'

    @classmethod
    def generate_id(cls) -> NanoIdType:
        return NanoId.gen(abbrev=cls.__pk_abbrev__)


def import_model_modules() -> list[Any]:
    """
    Used by things like Alembic and Shell to bring in the relevant models
    Looks for `models.py` in directories registered.
    """
    model_modules = []
    for app in settings.BOUNDARIES:
        import_path = f'{settings.BASE_MODULE}.{app}.models'
        logger.debug(f'importing: {import_path}')
        module = import_module(import_path)
        model_modules.append(module)

    return model_modules


class BaseVersionedModelMixin(DeclarativeBase):
    """
    light weight version ID management mixin for models where you want multiple instances in the DB to be related
    to one another. Be default uses all the base model query operations, but provides specific interface to get
    work w/ objects that relate to one another by the version ID
    """

    __gl_version_pk_abbrev__: str = NotImplemented
    query_manager: Type[CurrentVersionManager] = CurrentVersionManager

    @declared_attr
    def global_version_id(cls) -> Mapped[str]:
        if cls.__gl_version_pk_abbrev__ == NotImplemented:
            raise NotImplementedError(f'__pk_abbrev__ must be implemented for {cls.__name__}')
        return mapped_column(
            String(length=50), nullable=False, server_default=text(f"gen_nanoid('{cls.__gl_version_pk_abbrev__}')")
        )

    @declared_attr
    def deleted_at(cls) -> Mapped[Optional[datetime]]:
        return mapped_column(DateTime(timezone=True), nullable=True, default=None)

    @classmethod
    def all_versions(cls) -> Type['BaseVersionedModelMixin']:
        cls.query_manager = BaseQueryManager  # type: ignore[assignment]
        return cls

    @classmethod
    def create_new_version(cls, domain_obj: CreateDomainType, global_version_id: NanoIdType) -> Any:
        """
        create new instance of an object linked to prior via the version ID on the object.
        """
        if not hasattr(cls, 'global_version_id') or not hasattr(cls, 'deleted_at'):
            raise AttributeError(f"{cls.__name__} must have 'global_version_id' and 'deleted_at' attributes")
        # Add global_version_id to the domain object
        domain_dict = domain_obj.to_dict()
        domain_dict['global_version_id'] = global_version_id
        # Type ignore because we're accessing methods through mixin indirection
        cls.all_versions().bulk_update(  # type: ignore[attr-defined]
            clauses=[cls.global_version_id == global_version_id, cls.deleted_at == None],
            updates=dict(deleted_at=datetime.now()),
        )
        # Recreate domain object with global_version_id
        # Using Any return type due to complex mixin inheritance
        return cls.create(domain_obj)  # type: ignore[attr-defined]
