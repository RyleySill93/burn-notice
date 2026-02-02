def instrument_server():
    from src import settings

    if settings.TELEMETRY_ENABLED:
        from ddtrace import config, patch_all

        config.env = settings.ENVIRONMENT
        config.service = 'app-backend'
        patch_all(
            aioredis=True,
            asyncio=True,
            boto=True,
            dramatiq=True,
            psycopg=True,
            redis=True,
            requests=True,
            sqlalchemy=True,
            jinja2=True,
            starlette=True,
            loguru=True,
            fastapi=True,
        )
        from ddtrace import tracer
        from ddtrace.filters import FilterRequestsOnUrl

        tracer.configure(
            settings={
                'FILTERS': [
                    FilterRequestsOnUrl(r'http://.*/healthcheck/api'),
                ],
            }
        )

        from src.version import VERSION

        config.version = VERSION
