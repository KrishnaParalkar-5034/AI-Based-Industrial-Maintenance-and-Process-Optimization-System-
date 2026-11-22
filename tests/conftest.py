"""
Pytest session configuration and database isolation fixture.
Forces all automated tests to execute against an isolated temporary SQLite database,
preventing any test pollution of the live application historian.
"""
import os
import tempfile
import pytest

# Allocate temporary database file path before application imports
_test_db_file = tempfile.NamedTemporaryFile(suffix="_test_historian.db", delete=False)
_test_db_path = _test_db_file.name
_test_db_file.close()

# Force environment variable before backend modules load
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"

from backend.db import Base, engine, SessionLocal


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """Create fresh isolated tables for test session and cleanup afterwards."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        if os.path.exists(_test_db_path):
            os.remove(_test_db_path)
    except Exception:
        pass
