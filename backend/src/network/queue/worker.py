from src.network.queue.telemetry import instrument_worker

# Do this first
instrument_worker()


from src import settings, setup

# Setups up application and broker
setup.run()

from importlib import import_module

import dramatiq
from loguru import logger


def _import_task_modules():
    model_modules = []
    # @TODO Better way not manually specify this import?
    import_module(f'{settings.BASE_MODULE}.platform.email.tasks')
    for app in settings.BOUNDARIES:
        try:
            module = import_module(f'{settings.BASE_MODULE}.{app}.tasks')
        except ModuleNotFoundError as exc:
            if settings.BASE_MODULE not in exc.args[0]:
                raise exc

            logger.warning(exc)
        else:
            model_modules.append(module)

    return model_modules


_import_task_modules()

# We are only going to use this global broker.
# If your task doesnt show up here... you are dead 💀
# This is likely because the tasks.py file is not specified in boundaries
registered_tasks = {f'{task.fn.__module__}.{name}': task for name, task in dramatiq.broker.global_broker.actors.items()}

logger.info('registered tasks:\n' + str(list(registered_tasks.keys())))
