from math import ceil
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Sequence, Tuple, Type, TypeVar, Union

# Complex SQLAlchemy repository pattern with many type system limitations
from loguru import logger
from sqlalchemy import desc, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.row import Row
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import InstrumentedAttribute, Query, Session
from sqlalchemy.sql.elements import BinaryExpression, ColumnElement, UnaryExpression

from src.common.domain import BaseDomain, SearchDomain
from src.network.database.repository.exceptions import (
    MultipleRepositoryObjectsFound,
    PreventingModelTruncation,
    RepositoryObjectNotFound,
)
from src.network.database.session import db

if TYPE_CHECKING:
    from src.common.model import BaseModel


class PaginatedResponse(BaseDomain):
    results: List[Dict[str, Any]]
    count: int
    page: int | None
    page_count: int | None
    page_size: int | None
    ordering: str | None = None


class BaseQueryManager:
    def __init__(self, model: Type['BaseModel']) -> None:  # type: ignore[type-arg]
        self.model = model

    def get_query(self, *clauses: Any, **specification: Any) -> 'Query[BaseModel]':  # type: ignore[type-arg]
        query = self.model._get_session().query(self.model)
        for clause in clauses:
            query = query.where(clause)
        for key, value in specification.items():
            query = self.model._parse_specification(query, key, value)
        return query


class CurrentVersionManager(BaseQueryManager):
    def get_query(self, *clauses: Any, **specification: Any) -> 'Query[BaseModel]':  # type: ignore[type-arg]
        clauses = list(clauses) + [self.model.deleted_at == None]  # type: ignore[attr-defined, assignment]
        return super().get_query(*clauses, **specification)


ReadDomainType = TypeVar('ReadDomainType', bound=BaseDomain)
CreateDomainType = TypeVar('CreateDomainType', bound=BaseDomain)
SearchDomainType = TypeVar('SearchDomainType', bound=SearchDomain)
QueryManagerType = TypeVar('QueryManagerType', bound=BaseQueryManager)


class RepositoryMixin(Generic[ReadDomainType, CreateDomainType]):
    """
    Database access layer. All interaction with the database should be routed
    through this layer. all public interfaces accept domains subclasses from the
    pydantic base class with orm_mode to true for simple domain -> orm mapping
    """

    __create_domain__: Type[CreateDomainType] = NotImplemented
    __read_domain__: Type[ReadDomainType] = NotImplemented
    query_manager: Type[BaseQueryManager] | None = BaseQueryManager

    @classmethod
    def _get_session(cls) -> Session:
        # logger.debug(f'using session id: {id(db.session)}')
        return db.session

    @classmethod
    def get_query(cls, *clauses: Any, **specification: Any) -> 'Query[BaseModel]':  # type: ignore[type-arg]
        if cls.query_manager is None:
            raise ValueError(f'query_manager not set for {cls.__name__}')
        return cls.query_manager(cls).get_query(*clauses, **specification)  # type: ignore[arg-type]

    @classmethod
    def get(cls, *clauses: Union[BinaryExpression[Any], ColumnElement[bool]], **specification: Any) -> ReadDomainType:
        instance = cls._get(*clauses, **specification)

        return cls._to_domain(instance)

    @classmethod
    def get_attribute(cls, attribute: InstrumentedAttribute[Any], *clauses: Any, **specification: Any) -> Any:
        """
        Retrieves a specific attribute for a single object that matches the given clauses and specification.
        :raises RepositoryObjectNotFound: If no object is found matching the criteria
        """
        query = cls.get_query(*clauses, **specification).with_entities(attribute)

        try:
            result = query.one()
            return result[0]  # Return the first (and only) column
        except NoResultFound:
            raise RepositoryObjectNotFound(f'{cls.__name__} with {specification} not found!')

    @classmethod
    def get_or_none(cls, *clauses: Any, **specification: Any) -> ReadDomainType | None:
        try:
            instance = cls._get(*clauses, **specification)
        except RepositoryObjectNotFound:
            return None

        return cls._to_domain(instance)

    @classmethod
    def _get(cls, *clauses: Any, **specification: Any) -> 'BaseModel[Any, Any]':
        try:
            return cls.get_query(*clauses, **specification).one()
            # assert one and only one object returned
        except MultipleResultsFound:
            raise MultipleRepositoryObjectsFound(f'Multiple results found for {cls.__name__}: {specification}!')
        except NoResultFound:
            raise RepositoryObjectNotFound(f'{cls.__name__}: {specification} not found!')

    @classmethod
    def latest(
        cls,
        *clauses: Any,
        by: 'InstrumentedAttribute[Any]' | List['InstrumentedAttribute[Any]'],
    ) -> ReadDomainType:
        if not isinstance(by, list):
            by = [by]

        query = cls.get_query(*clauses)

        # Sort the results in descending order based on each specified field
        for attribute in by:
            query = query.order_by(desc(attribute))

        # Retrieve and return the latest record (top record)
        latest_record = query.first()
        if latest_record is None:
            raise RepositoryObjectNotFound('No latest record found')

        return cls._to_domain(latest_record)

    @classmethod
    def list(
        cls,
        *clauses: Any,
        ordering: Optional[List[Union[str, UnaryExpression]]] = None,
        **specification: Any,  # type: ignore[type-arg]
    ) -> List[ReadDomainType]:
        query = cls.get_query(*clauses, **specification)
        if ordering:
            orders = cls._parse_ordering(ordering)
            query = query.order_by(*orders)
        return [cls._to_domain(obj) for obj in query]

    @classmethod
    def list_attribute(cls, attribute: str, *clauses: Any, **specification: Any) -> List[Any]:
        query = cls._list_attributes([attribute], *clauses, **specification)

        return [values_list[0] for values_list in query]

    @classmethod
    def list_attributes(
        cls,
        attributes: List[Union[str, InstrumentedAttribute[str]]],
        clauses: List[Any],
        **specification: Any,
    ) -> List[Row]:  # type: ignore[type-arg]
        return list(cls.get_query(*clauses, **specification).with_entities(*attributes))  # type: ignore[arg-type]

    @classmethod
    def list_paginated(
        cls,
        page_size: int | None,
        page: int | None,
        ordering: str | None,
        clauses: List[Any] | None = None,
    ) -> PaginatedResponse:
        # I think search/filtering is adapted into a specification upstream of this
        # search
        # filters
        clauses = list(clauses) if clauses else []
        query = cls.get_query(*clauses)
        count = query.count()

        query = cls._paginate_query(
            query=query,
            page_size=page_size,
            page=page,  # type: ignore[arg-type]
            ordering=ordering,
        )

        domain_objects = [cls._to_domain(obj).to_dict() for obj in query]

        return PaginatedResponse(
            results=domain_objects,
            count=count,
            page_size=page_size,
            page=page,
            page_count=ceil(count / page_size) if page_size else None,
            ordering=ordering,
        )

    @classmethod
    def count(cls, *clauses: Any, **specification: Any) -> int:
        query = cls.get_query(*clauses, **specification)
        return int(query.count())

    @classmethod
    def create(cls, domain_obj: CreateDomainType) -> ReadDomainType:
        model_instance = cls._create(**domain_obj.to_dict())
        return cls._to_domain(model_instance)

    @classmethod
    def bulk_create_nested(cls, domain_objs: List[CreateDomainType]) -> None:
        """
        Supports nesting of objects... I think? If not we should delete
        """
        model_instances = [cls(**domain_obj.to_dict()) for domain_obj in domain_objs]
        cls._get_session().add_all(model_instances)
        try:
            cls._get_session().flush(model_instances)
        except IntegrityError:
            cls._get_session().rollback()
            raise

    @classmethod
    def bulk_create(
        cls,
        domain_objs: List[CreateDomainType],
        chunk_size: int = 1000,
        returning: Sequence[str] | None = None,
    ) -> int:
        """
        Bulk create in chunks
        """
        # Ignore empty lists
        if len(domain_objs) == 0:
            return len(domain_objs)

        returning = returning or []
        chunks = cls._chunks(domain_objs, chunk_size)

        for chunk in chunks:
            mappings = [domain_obj.to_dict() for domain_obj in chunk]
            statement = insert(cls).values(mappings)
            if len(returning) > 0:
                statement = statement.returning(*returning)  # type: ignore[call-overload]
            try:
                cls._get_session().execute(statement)
            except IntegrityError:
                cls._get_session().rollback()
                raise
        return len(domain_objs)

    @classmethod
    def bulk_create_ignore(
        cls,
        mappings: Sequence[Dict[str, Any]],
        chunk_size: int = 1000,
    ) -> None:
        """
        Ignores conflicts any conflicts while creating
        """
        chunks = cls._chunks(mappings, chunk_size)  # type: ignore[arg-type]
        for chunk in chunks:
            statement = insert(cls).values(chunk).on_conflict_do_nothing()
            try:
                cls._get_session().execute(statement)
            except IntegrityError:
                cls._get_session().rollback()
                raise

    @classmethod
    def bulk_update_mappings(
        cls,
        mappings: Sequence[Dict[str, Any]],
        chunk_size: int = 1000,
    ) -> int:
        model_instance = cls.get_query().first()
        for mapping in mappings:
            for key, _ in mapping.items():
                if not hasattr(model_instance, key):
                    raise ValueError(f"The key '{key}' is not a valid attribute for this model.")
        """
        Bulk update using a dictionary that contains primary key and fields that
        need to be updated.
        """
        if not mappings:
            return len(mappings)

        # @TODO Returning not working here
        # https://github.com/sqlalchemy/sqlalchemy/discussions/7980#discussion-4046124
        statement = update(cls)
        # @TODO This is skipping validation making it semi-dangerous
        chunks = cls._chunks(mappings, chunk_size)  # type: ignore[arg-type]
        for chunk in chunks:
            try:
                cls._get_session().execute(statement, chunk)
            except IntegrityError:
                cls._get_session().rollback()
                raise

        return len(mappings)

    @classmethod
    def get_or_create(
        cls,
        defaults: Dict[str, Any] | None = None,
        **specification: Any,
    ) -> Tuple[ReadDomainType, bool]:
        defaults = defaults or {}
        # kinda gross to use the specification as a payload to create an object but ¯\_(ツ)_/¯
        try:
            domain_instance = cls.get(**specification)
            return domain_instance, False
        except RepositoryObjectNotFound:
            pass

        model_instance = cls._create(
            **specification,
            **defaults,
        )
        return cls._to_domain(model_instance), True

    @classmethod
    def delete(cls, *clauses: Union[BinaryExpression[Any], ColumnElement[bool]], **specification: Any) -> int:
        if specification:
            logger.warning(f'specification kwargs for {cls.__name__}.delete is deprecated please dont use!')

        if not clauses and not specification:
            # if clauses is None or specification is None:
            raise PreventingModelTruncation(f'Must pass clauses to avoid truncating {cls.__name__}')

        # Ensure clauses like and_([]) or or_([]) that ultimately evaluate to nothing are checked as well
        non_empty_clauses = False
        if clauses:
            for clause in clauses:
                compiled = str(clause.compile())
                if compiled:
                    non_empty_clauses = True
                    break

        if clauses and not non_empty_clauses:
            raise PreventingModelTruncation(f'Empty clauses would cause truncating {cls.__name__}!')

        try:
            return cls.get_query(*clauses, **specification).delete()
        except IntegrityError:
            cls._get_session().rollback()
            raise

    @classmethod
    def update(cls, id: str, **updates: Any) -> ReadDomainType:
        model_instance = cls.get_query(id=id).one()
        for key, value in updates.items():
            if not hasattr(model_instance, key):
                raise ValueError(f"The key '{key}' is not a valid attribute for this model.")
            setattr(model_instance, key, value)

        try:
            cls._get_session().flush([model_instance])
        except IntegrityError:
            cls._get_session().rollback()
            raise

        return cls.get(cls.id == id)  # type: ignore[attr-defined]

    @classmethod
    def update_or_create(cls, updates: Dict[str, Any] | None = None, **specification: Any) -> ReadDomainType:
        """
        If an object with this specification does not exist, create it according to the specification + updates.
        Otherwise, update that object.
        """
        instance, created = cls.get_or_create(defaults=updates, **specification)

        if not created:
            return cls.update(id=instance.id, **updates)  # type: ignore[arg-type, attr-defined]

        return instance

    @classmethod
    def bulk_update(cls, updates: Dict[str, Any], clauses: List[Any]) -> None:
        cls.get_query(*clauses).update(updates)  # type: ignore[arg-type]

    @classmethod
    def _create(cls, **attributes: Any) -> 'BaseModel[Any, Any]':
        model_instance = cls(**attributes)
        cls._get_session().add(model_instance)
        try:
            cls._get_session().flush([model_instance])
        except IntegrityError:
            cls._get_session().rollback()
            raise

        return model_instance  # type: ignore[return-value]

    @classmethod
    def _paginate_query(
        cls,
        query: 'Query[BaseModel[Any, Any]]',
        page: int,
        page_size: int | None = None,
        ordering: str | None = None,
    ) -> 'Query[BaseModel[Any, Any]]':
        ordering_list = [ordering] if ordering else []
        parsed_ordering = cls._parse_ordering(ordering_list)  # type: ignore[arg-type]
        if parsed_ordering:
            query = query.order_by(*parsed_ordering)

        if page_size:
            return query.limit(page_size).offset((page - 1) * page_size)

        return query

    @classmethod
    def _parse_ordering(
        cls, ordering: List[Union[str, 'UnaryExpression[Any]']] | None = None
    ) -> List['UnaryExpression[Any]']:
        """
        Parses str references for a field like:
        ['-effective_date', 'amount']
        """
        order_expressions = []
        if ordering:
            for order in ordering:
                if isinstance(order, str):
                    if order[0] == '-':
                        # Get rid of first character
                        ordering_attr = getattr(cls, order[1:])
                        order_expressions.append(ordering_attr.desc())
                    else:
                        ordering_attr = getattr(cls, order)
                        order_expressions.append(ordering_attr.asc())
                else:
                    # Assume already an expression
                    order_expressions.append(order)

        return order_expressions

    @classmethod
    def _parse_specification(cls, query: Any, key: Any, value: Any) -> Any:
        """
        Parses str references for a field like:
        """
        return query.where(getattr(cls, key) == value)

    @classmethod
    def _list_attributes(
        cls,
        attributes: List[str],
        *clauses: Any,
        **specification: Any,
    ) -> List[Tuple[Any, ...]]:
        clauses = list(clauses) if clauses else []  # type: ignore[assignment]
        model_attributes = [getattr(cls, attr) for attr in attributes]
        return list(cls.get_query(*clauses, **specification).with_entities(*model_attributes))

    @classmethod
    def _to_domain(cls, model_instance: 'BaseModel[Any, Any]') -> ReadDomainType:
        return cls.__read_domain__.model_validate(model_instance)  # type: ignore[no-any-return]

    @classmethod
    def _chunks(cls, lst: List[Any], chunk_size: int) -> Any:
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), chunk_size):
            yield lst[i : i + chunk_size]

    @classmethod
    def bulk_update_or_create_with_recursive_foreign_keys(
        cls, updates: List[Dict[str, Any]], recursive_foreign_key_column_names: List[str]
    ) -> None:
        """
        Bulk update or create objects with support for recursive foreign keys.
        """
        updates_by_id = {update['id']: {k: v for k, v in update.items() if k != 'id'} for update in updates}
        processed_ids = set()

        def _create_or_update_recur(id: str) -> None:
            if id in processed_ids or id not in updates_by_id:
                return

            update_params = updates_by_id[id]

            for fk_column_name in recursive_foreign_key_column_names:
                if fk_id := update_params.get(fk_column_name):
                    if fk_id == id:
                        raise ValueError(f'Circular self-reference detected for {id}')

                    _create_or_update_recur(fk_id)

            cls.update_or_create(update_params, id=id)

            processed_ids.add(id)

        for params in updates:
            _create_or_update_recur(params['id'])
