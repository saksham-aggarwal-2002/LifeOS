"""Database: where the file lives, creating its tables, daily backups."""
import os
import shutil
import sqlite3
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
# Your data lives in LifeOS_data, next to (not inside) the app's folder: it's
# yours, and the app is only a way to view and edit it. While changing the app,
# it uses test_data (mock data) inside the app's folder instead: which one is
# chosen in Settings (app/datafolder.py), and use() switches between them.
# LIFEOS_DATA_DIR fixes it to some other folder (tests, the UI test harness).
YOUR_DATA_DIR = PROJECT_DIR.parent / "LifeOS_data"
TEST_DATA_DIR = PROJECT_DIR / "test_data"


def use(folder):
    """Point everything at `folder`: the database, backups and text files in it."""
    global DATA_DIR, DB_PATH, BACKUP_DIR
    DATA_DIR = Path(folder)
    DB_PATH = DATA_DIR / "lifeos.db"
    BACKUP_DIR = DATA_DIR / "backups"


use(os.environ.get("LIFEOS_DATA_DIR", YOUR_DATA_DIR))

SCHEMA_DIR = PROJECT_DIR / "schema"
# One file per tab, each defining that tab's tables as they are now.
SCHEMA_FILES = ["todo.sql", "gym.sql", "food.sql", "body.sql"]
BACKUPS_TO_KEEP = 14


def connect(path=None):
    """Open the database (creating its tables if it's new) and return the connection."""
    path = path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: pywebview calls Python from its own threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # rows behave like dicts: row["title"]
    conn.execute("PRAGMA foreign_keys = ON")  # makes ON DELETE CASCADE work
    if _shape(conn):
        check_schema(conn)
    else:
        create(conn)
    return conn


def schema_files():
    return [SCHEMA_DIR / name for name in SCHEMA_FILES]


def create(conn):
    """Make every table in schema/, all at once: a broken file leaves nothing."""
    sql = "\n".join(path.read_text() for path in schema_files())
    try:
        conn.executescript(f"BEGIN;\n{sql}\nCOMMIT;")
    except Exception:
        conn.rollback()
        raise


def _shape(conn):
    """Every table's columns, links and unique indexes: what has to match
    schema/ (comments and row order don't count)."""
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    return {
        t: (
            [tuple(c)[1:] for c in conn.execute(f"PRAGMA table_info({t})")],
            sorted(tuple(f)[2:] for f in conn.execute(f"PRAGMA foreign_key_list({t})")),
            sorted((i[2], [c[2] for c in conn.execute(f"PRAGMA index_info({i[1]})")]) for i in conn.execute(f"PRAGMA index_list({t})")),
        )
        for t in tables
    }


def check_schema(conn):
    """Refuse a database whose tables no longer match schema/. Editing a schema
    file doesn't change an existing database: test data is made again
    (app/datafolder.py), your own is converted by a one-off script."""
    fresh = sqlite3.connect(":memory:")
    create(fresh)
    if _shape(conn) != _shape(fresh):
        raise RuntimeError(
            f"The tables in {conn.execute('PRAGMA database_list').fetchone()[2]} don't match schema/: "
            "the app has changed since it was made. "
            "Convert it to the new tables with a one-off script (test data is simply made again)."
        )


def backup(conn, backup_dir=None, keep=BACKUPS_TO_KEEP, folders=()):
    """Save one copy of the database per day, keeping the newest `keep`.
    `folders` (e.g. the journal's) are copied alongside as <name>-YYYY-MM-DD."""
    backup_dir = backup_dir or BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    target = backup_dir / f"lifeos-{today}.db"
    if not target.exists():
        with sqlite3.connect(target) as dest:
            conn.backup(dest)  # SQLite's own safe copy, even while in use
    for path in sorted(backup_dir.glob("lifeos-*.db"))[:-keep]:
        path.unlink()
    for folder in folders:
        prefix = folder.name.lower().replace(" ", "-")
        copy = backup_dir / f"{prefix}-{today}"
        if folder.exists() and not copy.exists():
            shutil.copytree(folder, copy)
        for path in sorted(backup_dir.glob(f"{prefix}-*"))[:-keep]:
            shutil.rmtree(path)
