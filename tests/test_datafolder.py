"""Settings switches the app between your own data folder and a test folder of
mock data. Here both are temp folders, and so is the file remembering the choice."""
import sqlite3

import pytest

from app import datafolder, db


@pytest.fixture
def folders(tmp_path, monkeypatch):
    """Personal and test folders in tmp_path, with switching allowed (no LIFEOS_DATA_DIR)."""
    monkeypatch.delenv("LIFEOS_DATA_DIR")
    for name in ("DATA_DIR", "DB_PATH", "BACKUP_DIR"):  # put back after db.use()
        monkeypatch.setattr(db, name, getattr(db, name))
    folders = {"personal": tmp_path / "personal", "test": tmp_path / "test"}
    monkeypatch.setattr(datafolder, "FOLDERS", folders)
    monkeypatch.setattr(datafolder, "CHOICE_FILE", tmp_path / "data_folder.txt")
    monkeypatch.setattr(datafolder, "error", None)
    return folders


def workouts(conn):
    return conn.execute("SELECT COUNT(*) FROM gym_log").fetchone()[0]


def change_schema(folder):
    """Make the folder's database no longer match the schema files."""
    conn = sqlite3.connect(folder / "lifeos.db")
    conn.execute("ALTER TABLE weights ADD COLUMN mood TEXT")
    conn.commit()
    conn.close()


def test_opens_your_own_folder_until_you_choose_test(folders):
    conn = datafolder.start()
    assert db.DATA_DIR == folders["personal"]
    assert workouts(conn) == 0  # never any mock data in your own folder
    assert (folders["personal"] / "README.md").exists()
    assert not folders["test"].exists()
    assert datafolder.status()["which"] == "personal"


def test_switching_to_test_fills_it_with_mock_data_and_is_remembered(folders):
    personal = datafolder.start()
    conn = datafolder.switch(personal, "test")
    assert db.DATA_DIR == folders["test"]
    assert workouts(conn) > 0
    assert list((folders["test"] / "Templates" / "Gym").glob("*.txt"))
    with pytest.raises(sqlite3.ProgrammingError):  # the old connection is closed
        personal.execute("SELECT 1")
    assert datafolder.chosen() == "test"
    conn.close()
    assert datafolder.start() and db.DATA_DIR == folders["test"]  # next launch


def test_switching_back_keeps_both_folders_as_they_were(folders):
    conn = datafolder.switch(datafolder.start(), "test")
    conn.execute("DELETE FROM gym_log WHERE id = (SELECT MIN(id) FROM gym_log)")
    conn.commit()
    left = workouts(conn)
    conn = datafolder.switch(conn, "personal")
    assert workouts(conn) == 0
    conn = datafolder.switch(conn, "test")
    assert workouts(conn) == left  # not refilled


def test_reset_test_data_starts_it_again(folders):
    conn = datafolder.switch(datafolder.start(), "test")
    full = workouts(conn)
    conn.execute("DELETE FROM gym_log")
    conn.commit()
    conn = datafolder.reset_test(conn)
    assert workouts(conn) == full


def test_reset_is_refused_on_your_own_folder(folders):
    conn = datafolder.start()
    with pytest.raises(ValueError, match="test folder"):
        datafolder.reset_test(conn)
    assert workouts(conn) == 0  # still open


def test_your_folder_out_of_date_opens_test_instead_and_says_why(folders):
    datafolder.start().close()
    change_schema(folders["personal"])
    conn = datafolder.start()
    assert db.DATA_DIR == folders["test"]
    assert workouts(conn) > 0
    assert "personal folder couldn't be opened" in datafolder.status()["error"]
    # Switching to it again is refused, and the test folder stays open.
    with pytest.raises(ValueError, match="don't match schema"):
        datafolder.switch(conn, "personal")
    assert db.DATA_DIR == folders["test"] and workouts(conn) > 0
    assert datafolder.chosen() == "personal"  # the choice is unchanged


def test_out_of_date_test_data_is_made_again(folders):
    conn = datafolder.switch(datafolder.start(), "test")
    conn.execute("DELETE FROM gym_log")
    conn.commit()
    conn.close()
    change_schema(folders["test"])
    conn = datafolder.start()
    assert db.DATA_DIR == folders["test"]
    assert workouts(conn) > 0  # fresh mock data, in the current tables
    assert "mood" not in [c["name"] for c in conn.execute("PRAGMA table_info(weights)")]


def test_set_by_lifeos_data_dir_it_cant_be_switched(folders, tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEOS_DATA_DIR", str(tmp_path / "fixed"))
    db.use(tmp_path / "fixed")
    conn = datafolder.start()
    assert db.DATA_DIR == tmp_path / "fixed"
    assert workouts(conn) == 0
    with pytest.raises(ValueError, match="LIFEOS_DATA_DIR"):
        datafolder.switch(conn, "test")
    assert not datafolder.CHOICE_FILE.exists()
    assert datafolder.status() | {"path": None} == {
        "which": None, "path": None, "folders": {k: str(v) for k, v in folders.items()}, "fixed": True, "error": None}
