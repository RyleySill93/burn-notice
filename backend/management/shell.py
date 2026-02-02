# https://www.pedaldrivenprogramming.com/2021/01/shell-plus-for-sqlalchemy/
import inspect as _inspect
import os
import sys

from colorama import Back, Fore, Style, init
from IPython import start_ipython  # type: ignore
from sqlalchemy import *  # noqa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ruff: noqa
from src import setup

setup.run()
# Patch IsolatedSession behavior so everything is merged to single session
from src.network.database import session as network_session

network_session.IsolatedSession = network_session.PatchedIsolatedSession
network_session.ReadOnlySession = network_session.PatchedReadOnlySession

import datetime  # noqa
import decimal  # noqa

from src.common import context
from src.common.model import import_model_modules
from src.network.database.session import db
from src.settings import ENVIRONMENT


def import_models():
    models = import_model_modules()
    for modul in models:
        members = _inspect.getmembers(modul)
        for name, member in members:
            # Is this a SQLAlchemy model?
            is_sqlalchemy_model = _inspect.isclass(member) and hasattr(member, '__tablename__')
            if is_sqlalchemy_model:
                globals()[name] = member


init(autoreset=True)  # Initialize colorama

_ENV_INFO_LOGGED = False


def print_environment_info():
    global _ENV_INFO_LOGGED
    if _ENV_INFO_LOGGED:
        return

    from src import settings

    print(f'\n{Fore.GREEN}{Back.BLACK}🚀 {settings.COMPANY_NAME} Application Shell 🚀{Style.RESET_ALL}')
    print(f"{Fore.GREEN}{Back.BLACK}{'=' * 40}{Style.RESET_ALL}")

    is_production = ENVIRONMENT.lower() == 'production'
    env_color = Fore.RED if is_production else Fore.GREEN
    env_text = f'{env_color}{Back.BLACK}{ENVIRONMENT}{Style.RESET_ALL}'
    print(f'{Fore.GREEN}{Back.BLACK}🌍 Environment:{Style.RESET_ALL} {env_text}')

    transaction_id = db.session.execute(text('SELECT txid_current()')).scalar()
    print(
        f'{Fore.GREEN}{Back.BLACK}🔒 DB Transaction ID:{Style.RESET_ALL} {Fore.GREEN}{Back.BLACK}{transaction_id}{Style.RESET_ALL}'
    )

    if is_production:
        warning = f'{Fore.RED}{Back.BLACK}💀⚠️  WARNING: You are in PRODUCTION environment! ⚠️ 💀{Style.RESET_ALL}'
        print(f'\n{warning}')

    print(f"{Fore.GREEN}{Back.BLACK}{'=' * 40}{Style.RESET_ALL}")

    _ENV_INFO_LOGGED = True


import_models()

context.initialize(
    user_type=context.AppContextUserType.MANUAL.value,
    user_id='user-engineer',
    breadcrumb='app shell',
)
with db(commit_on_success=False) as db:
    # Define a startup script for IPython
    startup_script = """
    ip = get_ipython()
    if ip is not None:
        ip.events.register('post_execute', print_environment_info)
    else:
        print("Warning: Unable to get IPython instance. Event registration failed.")
    """

    # Start IPython with the startup script
    start_ipython(colors='neutral', user_ns=globals(), exec_lines=[startup_script])
