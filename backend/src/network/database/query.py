from typing import Any, Generic, List, Optional, Sequence, TypeVar

from sqlalchemy import (
    BinaryExpression,
    CursorResult,
    Delete,
    Insert,
    Join,
    Result,
    ScalarResult,
    Select,
    Selectable,
)
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from src.common.model import BaseModel
from src.network.database.repository.exceptions import (
    MultipleRepositoryObjectsFound,
    RepositoryObjectNotFound,
)
from src.network.database.session import db

ModelType = TypeVar('ModelType', bound=BaseModel)


class ModelManager(Generic[ModelType]):
    def __init__(self, model: ModelType):
        self._model: ModelType = model
        self._session = None

    def __str__(self):
        return f'{self._model.__class__.__name__}ModelManager'

    def __repr__(self):
        return self.__str__()

    @property
    def session(self) -> Session:
        return db.session

    @property
    def joins(self) -> Sequence[Join]:
        return []

    @property
    def filters(self) -> Sequence[BinaryExpression]:
        return []

    def insert(self) -> Insert:
        return Insert(self._model)

    def select(self, *fields) -> Selectable:
        query = Select(self._model)
        return self._apply_defaults(query)

    @property
    def delete(self, *fields) -> Delete:
        query = Delete(self._model)
        return self._apply_filters(query)

    def _apply_joins(self, query: Any) -> Any:
        for join in self.joins:
            ...

        return query

    def _apply_filters(self, query: Any) -> Any:
        for filter in self.filters:
            ...

        return query

    def _apply_defaults(self, query: Any) -> Any:
        query = self._apply_joins(query)
        query = self._apply_filters(query)
        return query

    def execute(self, query: Any) -> Result:
        return self.session.execute(query)

    def get(self, **specification: Any) -> dict:
        try:
            return self.session.execute(
                self._apply_filters(self._apply_joins(self.select())).filter_by(**specification).limit(1)
            ).scalar_one()
        except MultipleResultsFound:
            raise MultipleRepositoryObjectsFound(f'Multiple results found for {self._model.__name__}: {specification}!')
        except NoResultFound:
            raise RepositoryObjectNotFound(f'{self._model.__name__}: {specification} not found!')

    def get_model(self, **specification: Any) -> dict:
        try:
            return self.session.execute(
                self._apply_filters(self._apply_joins(self.select())).filter_by(**specification).limit(1)
            ).scalar_one()
        except MultipleResultsFound:
            raise MultipleRepositoryObjectsFound(f'Multiple results found for {self._model.__name__}: {specification}!')
        except NoResultFound:
            raise RepositoryObjectNotFound(f'{self._model.__name__}: {specification} not found!')

    def list(self, **specification: Any) -> ScalarResult:
        return self.session.execute(self.select().filter_by(**specification).limit(1)).scalars()

    def list_attribute(self, attribute: str, **specification: Any) -> List[Any]:
        query = self._list_attributes(attribute, **specification)

        return [values_list[0] for values_list in query]

    def list_attributes(
        self,
        *attributes: list[str],
        **specification: Any,
    ) -> List[tuple[Any]]:
        query = self._list_attributes(*attributes, **specification)

        return list(query)

    def _list_attributes(
        self,
        *attributes: list[str],
        **specification: Any,
    ) -> List[tuple[Any]]:
        model_attributes = [getattr(self._model, attr) for attr in attributes]
        return list(self.select(*model_attributes).filter_by(**specification))

    def count(self, **specification: Any) -> int:
        query = self.select().filter_by(**specification)
        return int(query.count())

    def create(self, **fields) -> dict:
        result = self._create(**fields)
        return {'id': result.inserted_primary_key[0], **fields}

    def create_from_model(self, model: ModelType) -> ModelType:
        self.session.add(model)
        self.session.flush()
        return model

    def bulk_create_from_models(
        self,
        models: List[ModelType],
    ) -> List[ModelType]:
        self.session.add_all(models)
        self.session.flush(models)
        return models

    def get_or_create(
        self,
        defaults: Optional[dict[str, Any]] = None,
        **specification: Any,
    ) -> tuple[dict, bool]:
        defaults = defaults or {}
        try:
            model_instance = self.get(**specification)
            return model_instance, False
        except RepositoryObjectNotFound:
            pass

        fields = {
            **specification,
            **defaults,
        }
        result = self._create(**fields)
        fields['id'] = result.inserted_primary_key[0]

        return fields, True

    # idk how to handle updates
    # def update_or_create(
    #     self, domain_obj: BasePydanticDomain, defaults: Optional[dict] = None
    # ):
    #     return self._model.repository_objects.update_or_create(
    #         **domain_obj.to_dict(), defaults=defaults
    #     )

    # def update(self, domain_obj: BaseDomain):
    #     query = self.get_query(id=domain_obj.id)
    #     self._update(query, domain_obj)
    #     return self.get(id=query.get().id)

    # def bulk_update(self, objs: List[BasePydanticDomain], fields: List):
    #     model_instances = [self._model(**obj.to_dict()) for obj in objs]
    #     return self._model.repository_objects.bulk_update(
    #         model_instances, fields=fields
    #     )

    def _create(self, **values) -> CursorResult:
        query = self.insert().values(**values)
        return self.session.execute(query)
