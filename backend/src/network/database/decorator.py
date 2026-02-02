from starlette.routing import Route

from src.network.database.session import DatabaseMode

_ROUTE_DATABASE_MODE_KEY = '_database_mode'


def read_only_route(func):
    """
    Marks a fastapi route as read-only for database access.
    This decorator sets a flag on the route handler that is checked by
    Middleware to determine the type of database access.

    Example:
        @read_only
        @router.get("/users")
        def get_users():
            return db.session.query(User).all()
    """
    setattr(func, _ROUTE_DATABASE_MODE_KEY, DatabaseMode.READ_ONLY)
    return func


def route_database_mode_checker(route: Route) -> DatabaseMode | None:
    if not isinstance(route, Route):
        return DatabaseMode.READ_WRITE

    endpoint_func = route.endpoint
    database_mode = getattr(endpoint_func, _ROUTE_DATABASE_MODE_KEY, DatabaseMode.READ_WRITE)
    return database_mode
