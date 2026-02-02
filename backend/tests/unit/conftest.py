from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_db_access():
    """
    Unit tests should not be able to connect to the database
    """

    with patch(
        'src.network.database.session._rw_engine.connect',
        side_effect=Exception('🛑 Database access attempted! 🛑\n Not permitted during unit tests!'),
    ):
        yield
