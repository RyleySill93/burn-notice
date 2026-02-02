from threading import local
from typing import Dict, List

from dramatiq.middleware import Middleware
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.routing import Match
from starlette.types import ASGIApp

from src.network.database.decorator import route_database_mode_checker
from src.network.database.session import DatabaseMode, db


class HTTPSessionManagerMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        commit_on_success: bool = True,
    ):
        super().__init__(app)
        self.commit_on_success = commit_on_success
        self._route_groups = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        database_mode = self._determine_database_mode(request=request)
        with db(commit_on_success=self.commit_on_success, mode=database_mode):
            response = await call_next(request)
            if response.status_code >= 400:
                db.session.rollback()

        return response

    def _determine_database_mode(self, request: Request) -> DatabaseMode:
        """
        Determines database mode so we don't unnecessarily create connection
        overhead on the primary database and route directly to the RO DB for
        read-only designated routes.
        """
        # Match a route with the request to determine database mode
        matched_route = self._match_route(request=request)
        if matched_route:
            database_mode = route_database_mode_checker(matched_route)
        else:
            # We should never have an unmatched route but default to read / write
            database_mode = DatabaseMode.READ_WRITE

        return database_mode

    def _match_route(self, request: Request):
        """
        In starlette all route matching occurs after middlewares run
        This means we cant access the underlying route within a middleware
        which is being tracked here: https://github.com/encode/starlette/issues/685

        This matching strategy adds negligible overhead ~30μs after the first run
        It uses groups to cut down the possible matches.
        """
        # Cached route groups
        if not self._route_groups:
            request.app.route_groups = self._group_routes_by_first_path_segment(request.app.routes)

        # Get first path segment from request
        path_parts = request.url.path.split('/')
        first_part = next((part for part in path_parts if part), '')

        # Get candidate routes to check (either matching group or parameterized routes)
        routes_to_check = request.app.route_groups.get(first_part, []) + request.app.route_groups.get('_params', [])

        # Find matching route from smaller subset
        matched_route = None
        for route in routes_to_check:
            match, updated_scope = route.matches(request.scope)
            if match == Match.FULL:
                matched_route = route
                break

        return matched_route

    def _group_routes_by_first_path_segment(self, routes: List[APIRoute]) -> Dict[str, List[APIRoute]]:
        """
        Group routes by their first path segment for faster route matching.
        """
        grouped: Dict[str, List[APIRoute]] = {}

        for route in routes:
            # Find first non-empty path segment (skipping leading /)
            parts = route.path.split('/')
            first_part = next((part for part in parts if part), '')

            # Handle routes with parameter as first segment like /{param}/...
            if first_part.startswith('{'):
                first_part = '_params'

            if first_part not in grouped:
                grouped[first_part] = []
            grouped[first_part].append(route)

        return grouped


class DramatiqSessionMiddleware(Middleware):
    """
    Manages the default sqlalchemy session for dramatiq
    Similar pattern to dramatiq.middleware.CurrentMessage
    """

    session_manager_storage = local()

    def before_process_message(self, broker, message):
        session_manager = db(commit_on_success=True)
        setattr(self.session_manager_storage, 'session_manager', session_manager)
        session_manager.enter()

    def after_process_message(self, broker, message, *, result=None, exception=None):
        session_manager = getattr(self.session_manager_storage, 'session_manager')
        session_manager.exit(exception=exception)
        delattr(self.session_manager_storage, 'session_manager')
