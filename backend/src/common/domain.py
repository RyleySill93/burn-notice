from abc import abstractmethod
from decimal import Decimal
from typing import Any, Dict, Type

from humps import camelize  # type: ignore[attr-defined]
from pydantic import BaseModel, ConfigDict


def to_camel(string: str) -> str:
    return camelize(string)


BaseDomainConfig = ConfigDict(
    extra='forbid',
    use_enum_values=True,
    from_attributes=True,
    alias_generator=to_camel,
    populate_by_name=True,
)


class BaseDomain(BaseModel):
    model_config = BaseDomainConfig

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def get_provided_fields(self) -> Dict[str, Any]:
        """
        Return only fields that were explicitly provided in the input data.

        This distinguishes between:
        - Fields with default values that were NOT provided (excluded)
        - Fields explicitly set to None/null (included)

        Useful for:
        - Partial updates (only update provided fields)
        - Import operations (distinguish "not provided" vs "explicitly null")
        - Conditional logic based on what user actually sent

        Example:
            # Frontend sends: {"name": "John", "age": null}
            # Domain has: name: str, age: Optional[int] = None, email: Optional[str] = None

            obj.to_dict()  # {"name": "John", "age": None, "email": None}
            obj.get_provided_fields()  # {"name": "John", "age": None}  (email excluded)

        Returns:
            Dictionary with only explicitly provided fields
        """
        return self.model_dump(exclude_unset=True)

    def was_field_provided(self, field_name: str) -> bool:
        """
        Check if a specific field was explicitly provided in the input data.

        Returns True if field was in the original input (even if set to None/null).
        Returns False if field was not provided and got its default value.

        Args:
            field_name: Name of the field to check

        Returns:
            True if field was explicitly provided, False otherwise

        Example:
            # Frontend sends: {"name": "John", "age": null}
            # Domain has: name: str, age: Optional[int] = None, email: Optional[str] = None

            obj.was_field_provided("name")   # True
            obj.was_field_provided("age")    # True (explicitly null)
            obj.was_field_provided("email")  # False (not provided, got default)
        """
        return field_name in self.model_fields_set

    def __repr_str__(self, join_str: str) -> str:  # type: ignore[override]
        tab = '\n    '
        return (
            tab
            + f'{join_str}{tab}'.join(repr(v) if a is None else f'{a}={v!r}' for a, v in self.__repr_args__())
            + '\n'
        )


class SearchDomain(BaseDomain):
    """
    base domain for search based read ops to include search rank/other helpful search metadata. let pydantic
    coerce the obj_instance to it's inherited type
    """

    domain_obj: Type[BaseDomain]
    # text search rank using ts_rank_cd w/ multiple language vectors and doing a exact match + starts with
    unified_score: Decimal
    # used to tie-break across multiple domain text searches. Global search needs ot be able
    # to pick .1 vs .1 without knowing how the domain implemented search, so this composite
    # is a simple alphabetical preference for the first char of the field the model is searching
    composite_score: Decimal
    # copied from various places in each domain's data to this top level object to ensure easy use and organization
    # across various FE uses
    search_value: str

    @staticmethod
    @abstractmethod
    def get_search_field_value() -> str:
        """
        each domain that implements search as part of global search must define
        what data was searched on so we can surface in search. this is done w/ a str that will be used
        to fetch the data off the model
        """
        raise NotImplementedError

    @classmethod
    def factory(
        cls,
        obj_instance: Type[BaseDomain],
        unified_score: Decimal,
        composite_score: Decimal,
        search_value: str,
    ) -> 'SearchDomain':
        return cls(
            domain_obj=obj_instance,
            unified_score=unified_score,
            composite_score=composite_score,
            search_value=search_value,
        )
