from typing import List, Optional, Union

import polars as pl
from sqlalchemy.orm.session import Session as SqlAlchemySession

from src import settings
from src.network.database.session import db


class _DataframeQuery:
    """
    Singleton that provides polars database reading functionality with session support.
    Uses pl.read_database_uri internally but respects the current session context.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __call__(
        self,
        query: Union[str, List[str]],
        session: Optional[SqlAlchemySession] = None,
        use_active_session: bool = False,
        schema_overrides: Optional[dict] = None,
    ) -> Union[pl.DataFrame, List[pl.DataFrame]]:
        """
        Read database using polars with session support.

        Args:
            query: SQL query string or list of query strings
            session: Optional SQLAlchemy session. If None, uses the current session from db.session
            use_active_session: If True, uses session connection (sees uncommitted data).
                               If False, uses URI connection (better performance).

        Returns:
            DataFrame or list of DataFrames depending on input query type
        """
        schema_overrides = schema_overrides or dict()
        # Use provided session or fall back to the current session context
        active_session = session if session is not None else db.session
        if settings.IS_TESTING:
            # We always want to use this during tests since we dont commit data during
            # integration tests. This is gross but we want the rust gain.
            use_active_session = True

        if use_active_session:
            # Use read_database with the session's connection to see uncommitted data
            if isinstance(query, list):
                dfs = []
                for q in query:
                    df = pl.read_database(
                        q,
                        active_session.connection(),
                        schema_overrides=schema_overrides,
                    )
                    dfs.append(df)
                # Concatenate all DataFrames into one
                if dfs:
                    # Handle schema mismatches by using diagonal concatenation
                    # This fills missing columns with null values
                    return pl.concat(dfs, how='diagonal_relaxed')
                else:
                    return pl.DataFrame()
            else:
                return pl.read_database(query, active_session.connection(), schema_overrides=schema_overrides)
        else:
            # Use read_database_uri for better performance
            uri = active_session.connection().engine.url.render_as_string(hide_password=False)
            result = pl.read_database_uri(query=query, uri=uri, schema_overrides=schema_overrides)
            # read_database_uri already handles list concatenation internally
            return result


# Create the singleton instance
DataframeQuery = _DataframeQuery()
