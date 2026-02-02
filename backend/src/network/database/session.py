import sys
import time
from contextvars import ContextVar
from enum import Enum
from typing import Any, Callable, Dict, Optional

from loguru import logger
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session as SqlAlchemySession
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.compiler import FromLinter

from src import settings
from src.common import context


class DatabaseMode(Enum):
    READ_WRITE = 'read_write'
    READ_ONLY = 'read_only'


# Create separate engines for read-write and read-only
def create_db_engine(host: str) -> Engine:
    DATABASE_URI = URL.create(
        drivername='postgresql',
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=host,
        database=settings.DB_NAME,
    ).render_as_string(hide_password=False)

    return create_engine(
        DATABASE_URI,
        poolclass=NullPool,
        connect_args={
            'options': '-c timezone=utc -c statement_timeout=300000 -c idle_in_transaction_session_timeout=600000',  # 5 min statement, 10 min idle timeout
            'connect_timeout': 10,  # 10 second connection timeout
        },
        pool_pre_ping=True,  # Verify connections before use
        enable_from_linting=True,  # Ensures we check for Cartesians
        # echo=settings.DEBUG,
    )


_rw_engine = create_db_engine(settings.DB_HOST)
_ro_engine = create_db_engine(settings.DB_HOST_RO)

# Create session makers for each mode
_rw_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=_rw_engine)
_ro_session_maker = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_ro_engine,
)

if settings.DB_LOG_STATEMENTS:
    # Log statements and their execution times
    @event.listens_for(Engine, 'before_cursor_execute')
    def before_cursor_execute(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        conn.info.setdefault('query_start_time', []).append(time.time())
        if isinstance(parameters, list):
            # Handle list parameters differently
            # Maybe use string concatenation or a different approach
            stmt = statement
        else:
            # Only try string formatting with dictionaries
            stmt = statement % parameters
        logger.info(
            f'Start Query: {stmt}',
        )

    @event.listens_for(Engine, 'after_cursor_execute')
    def after_cursor_execute(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        total = time.time() - conn.info['query_start_time'].pop(-1)
        logger.info(f'Query Time: {total}')


# Context variables for session storage and mode
# Should be thread safe as well as coroutine safe!
_session_storage: ContextVar[SqlAlchemySession | None] = ContextVar('_session_storage', default=None)
_session_mode: ContextVar[DatabaseMode] = ContextVar('_session_mode', default=DatabaseMode.READ_WRITE)


@event.listens_for(_rw_session_maker, 'after_begin')
def receive_after_begin(session: SqlAlchemySession, transaction: Any, connection: Any) -> None:
    """
    Set app context after session begins for db audit
    """
    # System level audit
    user_type = context.get_user_type()
    user_id = context.get_user_id()
    impersonator_id = context.get_impersonator_id()
    request_id = context.get_request_id()
    # Application level audit
    event_id = context.get_event_id()
    event_type = context.get_event_type()
    breadcrumb = context.get_breadcrumb()
    event_context = context.get_event_context()

    if user_type == context.AppContextUserType.UNKNOWN:
        raise ValueError('Application context must be set before envoking change')

    # Prepare the audit context for batch statement
    sql_commands = []
    parameters: Dict[str, Any] = {}

    # User info
    sql_commands.append('set local auditcontext.user_type = :user_type')
    parameters['user_type'] = user_type.value  # Use enum value
    if user_id:
        # Certain routes will not be authenticated like login
        sql_commands.append('set local auditcontext.user_id = :user_id')
        parameters['user_id'] = user_id
    if impersonator_id:
        # Certain routes will not be authenticated like login
        sql_commands.append('set local auditcontext.impersonator_id = :impersonator_id')
        parameters['impersonator_id'] = impersonator_id

    # Meta info
    if request_id:
        sql_commands.append('set local auditcontext.request_id = :request_id')
        parameters['request_id'] = request_id
    if event_id:
        sql_commands.append('set local auditcontext.event_id = :event_id')
        parameters['event_id'] = event_id
    if event_type:
        sql_commands.append('set local auditcontext.event_type = :event_type')
        parameters['event_type'] = event_type
    if breadcrumb:
        sql_commands.append('set local auditcontext.breadcrumb = :breadcrumb')
        parameters['breadcrumb'] = breadcrumb

    if event_context:
        sql_commands.append('set local auditcontext.event_context = :event_context')
        parameters['event_context'] = event_context

    sql_statement = '; '.join(sql_commands)
    connection.execute(text(sql_statement), parameters)


class ImplicitCartesianDetected(Exception): ...


def raise_for_implicit_cartesians(self: Any, stmt_type: str = 'SELECT') -> None:
    """
    The default behavior for implicit cartesians is to warn, we want
    to raise instead.

    Implicit cartesian joins nearly always an undesirable outcome.
    They can produce an enormous result set full of duplicated, uncorrelated data.
    Most importantly, they increase the risk of IDDs

    A simplified version looks like:
    select book.name, author.name from book, author;
    """
    the_rest, start_with = self.lint()
    if the_rest:
        froms = the_rest
        if froms:
            template = (
                '{stmt_type}Implicit cartesian product detected between '
                'FROM element(s) {froms} and FROM element "{start}". '
                'To resolve this, apply appropriate join condition(s) '
                'between these elements. Cartesian products can lead to '
                'performance issues and unexpected result sets.'
            )
            froms_str = ', '.join(f'"{self.froms[from_]}"' for from_ in froms)
            message = template.format(
                stmt_type=f'{stmt_type} statement: ' if stmt_type else '',
                froms=froms_str,
                start=self.froms[start_with],
            )
            raise ImplicitCartesianDetected(message)


# Monkeypatch the warn method to raise errors instead of warnings for implicit cartesians
FromLinter.warn = raise_for_implicit_cartesians  # type: ignore[method-assign]

# @event.listens_for(_rw_session_maker, 'do_orm_execute')
# def do_audit_for_execute(session):
# """
# These context variables can be mutated at different stages of
# a transaction not just in the beginning.
# """
# This is called for each query and is excessive considering such
# a small surface area we update audit context for. In the future
# we might want to consider our own hook in the context manager.
# ...
# if session.is_select:
#     return
#
# # Otherwise lets make sure context is updated
# event_id = context.get_event_id()
# event_type = context.get_event_type()
# breadcrumb = context.get_breadcrumb()
# if event_id:
#     session.session.connection().execute(text(f"set local auditcontext.event_id = '{event_id}'"))
# if event_type:
#     session.session.connection().execute(text(f"set local auditcontext.event_type = '{event_type}'"))
# if breadcrumb:
#     session.session.connection().execute(text(f"set local auditcontext.breadcrumb = '{breadcrumb}'"))


class SessionNotAvailable(Exception):
    def __init__(self) -> None:
        msg = """
        Either you are not currently in a request context, or you need to manually 
        create a session context by using a `db` instance as a context manager e.g.:        
        with db():
            db.session.execute(Select(User))
        """
        super().__init__(msg)


class SessionManagerMeta(type):
    """
    Access session as a property on context manager
    without having to init
    """

    @property
    def session(self) -> SqlAlchemySession:
        """
        Make a thread and coroutine safe session
        """
        global _session_storage
        session = _session_storage.get()
        if session is None:
            raise SessionNotAvailable

        return session

    @property
    def mode(self) -> DatabaseMode:
        return _session_mode.get()


class SessionManager(metaclass=SessionManagerMeta):
    def __init__(
        self,
        session_kwargs: Dict[str, Any] | None = None,
        commit_on_success: bool = False,
        mode: DatabaseMode = DatabaseMode.READ_WRITE,
    ):
        self.session_token: Optional[Any] = None
        self.mode_token: Optional[Any] = None
        self.session_kwargs = session_kwargs or {}
        self.commit_on_success = commit_on_success
        self.mode = mode

    def enter(self) -> Any:
        global _session_storage, _session_mode

        # Set the database mode
        self.mode_token = _session_mode.set(self.mode)

        # Pytest as an example will create multiple sessions which will
        # create data in different sessions. Specifically this is the
        # case in API tests which will route through the session middleware
        # we use this to ensure the session is always shared
        if _session_storage.get() is None:
            session_maker = _rw_session_maker if self.mode == DatabaseMode.READ_WRITE else _ro_session_maker
            session = session_maker(**self.session_kwargs)
            self.session_token = _session_storage.set(session)

        # For read-only sessions - ensure no modifications can be made
        if self.mode == DatabaseMode.READ_ONLY:
            ro_session = _session_storage.get()
            if ro_session is None:
                raise SessionNotAvailable()
            # Used for testing purposes only!
            setattr(ro_session, '_is_read_only', True)

            @event.listens_for(ro_session, 'before_flush')
            def prevent_write_on_readonly(session: SqlAlchemySession, *args: Any, **kwargs: Any) -> None:
                if len(session.new) > 0 or len(session.deleted) > 0 or len(session.dirty) > 0:
                    raise RuntimeError('Cannot modify database in read-only mode')

        return type(self)

    def exit(self, exception: Exception) -> None:
        exc_type, exc_value, exc_tb = sys.exc_info()
        self.__exit__(exc_type, exc_value, exc_tb)

    def cleanup(self) -> None:
        global _session_storage
        session = _session_storage.get()
        if session is not None:
            session.close()
        if self.session_token:
            _session_storage.reset(self.session_token)
        if self.mode_token:
            _session_mode.reset(self.mode_token)

    def __enter__(self) -> Any:
        return self.enter()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        global _session_storage
        session = _session_storage.get()
        session_mode = _session_mode.get()
        is_success = exc_type is None

        if session is not None:
            if self.commit_on_success and is_success and session_mode == DatabaseMode.READ_WRITE:
                session.commit()
            else:
                session.rollback()

        self.cleanup()


# This is what external callers should access!
db: SessionManagerMeta = SessionManager


def on_commit(func: Callable[..., Any]) -> None:
    """
    Register function to be called after commit
    """
    # @TODO func must take in a session since sqlalchemy always passes it in
    event.listen(db.session, 'after_commit', func)


class IsolatedSession(SessionManager):
    """
    Meant to provide an isolated session away from the main application one above.
    Patches the existing session with a new one and replaces it in the end
    Use:
    with IsolatedSession(commit_on_success=False):
       # Do Stuff with New Session
       ...
    # Original session is replaced
    """

    def __init__(self, session_kwargs: Dict[str, Any] | None = None, commit_on_success: bool = False) -> None:
        super().__init__(session_kwargs=session_kwargs, commit_on_success=commit_on_success)
        self.current_session: Optional[SqlAlchemySession] = None

    def enter(self) -> Any:
        global _session_storage
        self.current_session = _session_storage.get()
        new_session = _rw_session_maker(**self.session_kwargs)
        self.session_token = _session_storage.set(new_session)

        return new_session

    def cleanup(self) -> None:
        super().cleanup()

        # Set the session back to the original
        global _session_storage
        _session_storage.set(self.current_session)


class PatchedIsolatedSession(IsolatedSession):
    """
    For tests and shell behavior, isolated sessions should not be used. This ensures
    the session being used in code, is the same as the global session and rolls back
    accordingly.
    """

    def enter(self) -> Any:
        global _session_storage
        return _session_storage.get()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        # Don't commit or rollback in tests - let the outer test transaction handle it
        # Don't call cleanup either - we don't own this session
        pass

    def cleanup(self) -> None:
        pass


class ReadOnlySession(SessionManager):
    """
    Provides an isolated read-only session that prevents any write operations.
    Similar to IsolatedSession but enforces DatabaseMode.READ_ONLY.

    Usage:
    with ReadOnlySession():
        # Do read-only operations
        results = db.session.query(Model).all()
        # Any write attempts will raise RuntimeError
    """

    def __init__(self, session_kwargs: Dict[str, Any] | None = None) -> None:
        # Force read-only mode and don't allow commit_on_success since we're read-only
        super().__init__(session_kwargs=session_kwargs, commit_on_success=False, mode=DatabaseMode.READ_ONLY)
        self.current_session: Optional[SqlAlchemySession] = None

    def enter(self) -> Any:
        global _session_storage, _session_mode

        # Store current session and mode
        self.current_session = _session_storage.get()

        # Create new read-only session
        new_session = _ro_session_maker(**self.session_kwargs or {})
        self.session_token = _session_storage.set(new_session)

        # Set read-only mode
        self.mode_token = _session_mode.set(DatabaseMode.READ_ONLY)

        return new_session

    def cleanup(self) -> None:
        super().cleanup()

        # Restore original session
        global _session_storage
        _session_storage.set(self.current_session)


class PatchedReadOnlySession(ReadOnlySession):
    """
    For tests and shell behavior, similar to PatchedIsolatedSession but maintains
    read-only enforcement.
    """

    def enter(self) -> Any:
        global _session_storage, _session_mode

        # Just set the mode to read-only while keeping the same session
        self.mode_token = _session_mode.set(DatabaseMode.READ_ONLY)
        return _session_storage.get()

    def cleanup(self) -> None:
        if self.mode_token:
            _session_mode.reset(self.mode_token)
