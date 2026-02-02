from src.common.middleware import DramatiqAuditMiddleware


def run():
    """
    Run before every entry point:
        fastapi server
        dramatiq worker
        dramatiq scheduler
        ipython shell
    """
    from loguru import logger

    from src import settings
    from src.common.logs import configure_logging

    configure_logging()
    configure_queue()
    configure_models()

    from src.platform.event.package import EventBus

    EventBus.initialize(settings.EVENT_BUS_SUBSCRIBER_REGISTRY)

    # The default here is bg:ansiyellow which you cant see in terminal
    if settings.ENVIRONMENT == 'local':
        from IPython.core.ultratb import VerboseTB

        orange = '#c96c0e'
        VerboseTB._tb_highlight = f'bg:{orange}'

    logger.info('application setup complete ✅')


def teardown():
    teardown_broadcast()


def configure_broadcast():
    """
    Sets up broadcaster which is used for communicating across
    deployments for things like websockets
    """
    from src.network.broadcaster.redis import initialize as initialize_redis_broadcaster

    initialize_redis_broadcaster()


def teardown_broadcast():
    """
    Tears down broadcaster which is used for communicating across
    deployments for things like websockets
    """
    from src.network.broadcaster.redis import teardown as teardown_redis_broadcaster

    teardown_redis_broadcaster()


def configure_websockets():
    from src.network.websockets.connection import (
        initialize as initialize_websocket_connection_manager,
    )

    connection_manager = initialize_websocket_connection_manager()
    return connection_manager


def configure_queue():
    """
    Sets up dramatiq broker with appropriate middleware
    """
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker
    from dramatiq.middleware import CurrentMessage
    from dramatiq.results import Results

    from src import settings
    from src.network.database.middleware import DramatiqSessionMiddleware
    from src.network.queue.broker import EagerBroker, StubBroker
    from src.network.queue.middleware import (
        DatadogTracingMiddleware,
        DramatiqJobStatusMiddleware,
        DramatiqTelemetryMiddleware,
        SentryMiddleware,
    )
    from src.network.queue.results import get_results_backend

    if settings.USE_MOCK_DRAMATIQ_BROKER:
        # Mocked broker
        broker = StubBroker()
        broker.emit_after('process_boot')
    elif settings.DRAMATIQ_EAGER_MODE:
        # Run tasks in main application thread
        # Useful for de-buggers
        broker = EagerBroker()
    else:
        # Live redis broker
        broker = RedisBroker(url=settings.REDIS_URL)

    # Middleware
    if settings.TELEMETRY_ENABLED:
        broker.add_middleware(DatadogTracingMiddleware())
    broker.add_middleware(DramatiqAuditMiddleware())
    broker.add_middleware(DramatiqTelemetryMiddleware())
    broker.add_middleware(DramatiqSessionMiddleware())
    broker.add_middleware(CurrentMessage())
    broker.add_middleware(SentryMiddleware())
    broker.add_middleware(DramatiqJobStatusMiddleware())
    broker.add_middleware(Results(backend=get_results_backend()))
    dramatiq.set_broker(broker)


def configure_models():
    """
    When using declarative we need to run this for our entry points
    to have context on our models / relationships example when
    traversing "user.id" as a foreign key
    """
    from src.common.model import import_model_modules

    import_model_modules()
