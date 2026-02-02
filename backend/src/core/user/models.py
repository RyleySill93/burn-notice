import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, func, literal_column, text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.model import BaseModel
from src.common.query import multi_field_search
from src.core.user.domains import AuthenticatedUserRead, UserCreate, UserRead


class User(BaseModel[UserRead, UserCreate]):
    first_name: Mapped[Optional[str]]
    last_name: Mapped[Optional[str]]
    email: Mapped[str] = mapped_column(String(length=320), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    # password can be null as some users don't use password login flow, just use magic links
    # or in the future using OAuth flows.
    hashed_password: Mapped[str] = mapped_column(String, nullable=True)
    archived_at: Mapped[datetime.date] = mapped_column(nullable=True)

    __pk_abbrev__ = 'user'
    __read_domain__ = UserRead
    __create_domain__ = UserCreate
    __system_audit__ = True

    __table_args__ = (
        Index('idx_search_user_email', func.to_tsvector(literal_column("'english'"), 'email'), postgresql_using='gin'),
        Index(
            'idx_search_user_email_simple',
            func.to_tsvector(literal_column("'simple'"), 'email'),
            postgresql_using='gin',
            info={'skip_autogenerate': True},
        ),
        Index(
            'idx_search_user_name',
            func.to_tsvector(
                literal_column("'english'"), text("COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')")
            ),
            postgresql_using='gin',
            info={'skip_autogenerate': True},
        ),
        Index(
            'idx_search_user_name_simple',
            func.to_tsvector(
                literal_column("'simple'"), text("COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')")
            ),
            postgresql_using='gin',
            info={'skip_autogenerate': True},
        ),
        Index('idx_user_email_lower', func.lower(text('email')), unique=True),
    )

    @classmethod
    def get_auth_user(self, *clauses, **specification: Any) -> AuthenticatedUserRead:
        instance = self._get(*clauses, **specification)

        return AuthenticatedUserRead.model_validate(instance)

    @classmethod
    def search(cls, search: str) -> list[UserRead]:
        query = cls.get_query()

        # Configure fields for search with their relative weights
        fields_config = [
            {'field': 'email', 'weight': 1.0, 'exact_match_score': 1000.0},
            {
                'field': func.concat_ws(' ', text('first_name'), text('last_name')),
                'weight': 0.8,
                'exact_match_score': 800.0,
            },
        ]

        # Perform the search
        query = multi_field_search(query=query, search=search, fields_config=fields_config, id_field=cls.id)

        results = query.all()

        return [
            UserRead(
                id=result[0].id,
                first_name=result[0].first_name,
                last_name=result[0].last_name,
                email=result[0].email,
                is_active=result[0].is_active,
                hashed_password=result[0].hashed_password,
                archived_at=result[0].archived_at,
            )
            for result in results
        ]


class HasUser:
    """
    Mixin for user relationships in other domains
    """

    user_id: Mapped[str] = mapped_column(ForeignKey('user.id'))

    @declared_attr
    def user(self) -> Mapped['User']:
        return relationship('User')
