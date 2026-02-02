from unittest.mock import PropertyMock, patch

from sqlalchemy.orm.session import Session

from src import setup
from src.common import context
from src.network.database import session as network_session
from src.network.database.session import db


class ApplicationMigrationSession:
    """
    Sets up the application session context
    for migrating data using service methods
    Example Use:
        from migrations.utils import ApplicationMigrationSession
        with ApplicationMigrationSession(op=op) as db:
            customers = CustomerService.factory().list()
            db.session.execute(text("select * from customer"))
    """

    def __init__(self, op):
        self.op = op
        self._original_session = network_session.IsolatedSession

    def __enter__(self):
        setup.configure_models()

        context.initialize(
            user_type=context.AppContextUserType.MANUAL.value,
            user_id='user-system',
            breadcrumb='migration',
        )

        # Patch IsolatedSession behavior so everything is merged to single session
        network_session.IsolatedSession = network_session.PatchedIsolatedSession
        network_session.ReadOnlySession = network_session.PatchedReadOnlySession

        # Start the session
        self.db_session = db(commit_on_success=False)
        self.db_session.enter()

        # Apply the patch to use same session as migration
        session = Session(bind=self.op.get_bind())
        self.mock_patch = patch('src.network.database.session.db', new_callable=PropertyMock)
        self.mock_session = self.mock_patch.start()
        self.mock_session.return_value = session

        # This should be patched and returning shared session now
        return db

    def __exit__(self, exc_type, exc_value, traceback):
        # Stop the patch
        if self.mock_patch:
            self.mock_patch.stop()

        # Ensure to exit db_session context manager
        self.db_session.exit(exc_value)

        # Restore the original IsolatedSession
        network_session.IsolatedSession = self._original_session
