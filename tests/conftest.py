"""Shared test setup: every test gets its own fresh database in a temp folder,
so tests never touch LifeOS_data and never affect each other."""
import os
import tempfile

# Before the app is imported, so every default path (database, backups...)
# starts out in a throwaway folder rather than your LifeOS_data.
os.environ["LIFEOS_DATA_DIR"] = tempfile.mkdtemp(prefix="lifeos-tests-")

import pytest

from app import db


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Files the app writes next to the database (e.g. Journal Entries) go to
    a temp folder too, never the real LifeOS_data."""
    folder = tmp_path / "data"
    monkeypatch.setattr(db, "DATA_DIR", folder)
    return folder


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()
