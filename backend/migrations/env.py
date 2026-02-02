from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.common.model import BaseModel, import_model_modules

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

import_model_modules()
target_metadata = BaseModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    from sqlalchemy.engine.url import URL

    from src import settings

    DATABASE_URI = URL.create(
        drivername='postgresql',
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        database=settings.DB_NAME,
    ).render_as_string(hide_password=False)
    return DATABASE_URI


class MissingMigrationMessage(Exception): ...


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    # Register audit functions and model attributes necessary for audit system
    from src.network.database.audit.ops import register_audit_metadata

    register_audit_metadata(target_metadata, BaseModel)
    from src.platform.audit.ops import register_audit_metadata

    register_audit_metadata(target_metadata, BaseModel)

    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()

    if hasattr(config.cmd_opts, 'message'):
        if not config.cmd_opts.message:
            raise MissingMigrationMessage("Missing migration message!\n Add with `make migrations m='some message'`")

    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    def include_object(object, name, type_, reflected, compare_to):
        # Skip autogenerate for specific user search indexes that have minor differences
        if type_ == 'index' and name in ['idx_search_user_name', 'idx_search_user_name_simple']:
            return False
        return True

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
