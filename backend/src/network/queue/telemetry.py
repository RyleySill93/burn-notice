def instrument_worker():
    from src import settings

    if settings.TELEMETRY_ENABLED:
        from ddtrace import config, patch_all

        config.env = settings.ENVIRONMENT
        config.service = 'app-worker'
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
            loguru=True,
        )
        from ddtrace import tracer

        tracer.configure()

        from src.version import VERSION

        config.version = VERSION
