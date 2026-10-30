"""The database foundation: creating it from schema/, backups and LifeOS_data/README.md."""
import sqlite3

import pytest

from app import datadoc, db


def test_new_database_gets_every_table(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"lists", "tasks", "gym_log", "exercises", "workout_sets", "food_log", "foods", "food_items", "weights"} <= tables


def test_reopening_creates_nothing_twice(tmp_path):
    db.connect(tmp_path / "t.db").close()
    conn = db.connect(tmp_path / "t.db")
    # The seeded "Tasks" list would be duplicated if the schema ran again.
    assert conn.execute("SELECT COUNT(*) FROM lists").fetchone()[0] == 1


def test_database_that_no_longer_matches_the_schema_is_refused(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("ALTER TABLE weights ADD COLUMN note TEXT")   # e.g. made before a schema edit
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="don't match schema"):
        db.connect(tmp_path / "t.db")


def test_broken_schema_creates_nothing(tmp_path, monkeypatch):
    schema = tmp_path / "schema"
    schema.mkdir()
    (schema / "todo.sql").write_text((db.SCHEMA_DIR / "todo.sql").read_text())
    (schema / "bad.sql").write_text("CREATE TABLE half (id INTEGER);\nNOT SQL;")
    monkeypatch.setattr(db, "SCHEMA_DIR", schema)
    monkeypatch.setattr(db, "SCHEMA_FILES", ["todo.sql", "bad.sql"])

    with pytest.raises(sqlite3.Error):
        db.connect(tmp_path / "t.db")

    conn = sqlite3.connect(tmp_path / "t.db")
    assert conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == []


def test_backup_once_per_day_and_old_ones_pruned(conn, tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    for day in range(1, 6):
        (backups / f"lifeos-2020-01-0{day}.db").write_text("")

    db.backup(conn, backups, keep=3)
    db.backup(conn, backups, keep=3)  # same day again: no second copy

    names = sorted(p.name for p in backups.iterdir())
    assert len(names) == 3
    assert names[-1].startswith("lifeos-20") and names[-1] > "lifeos-2020-01-05.db"  # today's is kept
    copy = sqlite3.connect(backups / names[-1])
    assert copy.execute("SELECT name FROM lists").fetchone()[0] == "Tasks"


def test_readme_describes_every_table_and_column(conn, data_dir):
    datadoc.write(conn)
    text = (data_dir / "README.md").read_text()
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        assert f"`{table}`" in text
        for col in conn.execute(f"PRAGMA table_info({table})"):
            assert f"| {col['name']} |" in text
    for tab in ("### To Do", "### Gym", "### Food", "### Body", "### Journal"):
        assert tab in text
    assert "unique, ignoring capitals" in text and "→ gym_log.id (deleted with it)" in text
    assert "Templates/Gym/<name>.txt" in text


def test_tests_never_use_your_data_folder():
    assert db.DATA_DIR.resolve() != db.YOUR_DATA_DIR.resolve()
    assert db.YOUR_DATA_DIR.resolve() not in db.DB_PATH.resolve().parents
    assert db.YOUR_DATA_DIR.resolve() not in db.BACKUP_DIR.resolve().parents
