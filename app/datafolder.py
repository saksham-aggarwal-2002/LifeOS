"""Which data folder the app is using, chosen in Settings:

    personal  LifeOS_data, next to the app's folder: your real data
    test      LifeOS/test_data, inside the app's folder: mock data, to try out
              changes to the app on without touching your own

The choice is kept in LifeOS/data_folder.txt, so the app opens on the same one
next time. A new test folder is filled with mock data (mock_data.py); "Reset
test data" deletes it and starts again, and so does opening it after a change
to the tables (schema/) that it no longer matches.

If LIFEOS_DATA_DIR is set (tests, the UI test harness), that folder is used
instead and can't be switched: the choice file is never read or written.
"""
import os
import shutil

import mock_data
from app import ai, datadoc, db, templates
from app.tabs import journal, todo

FOLDERS = {"personal": db.YOUR_DATA_DIR, "test": db.TEST_DATA_DIR}
CHOICE_FILE = db.PROJECT_DIR / "data_folder.txt"

# Why the app isn't on the chosen folder (e.g. your database no longer matches
# the schema after a change to the app), shown in Settings; None if it is.
error = None


def fixed():
    """True when LIFEOS_DATA_DIR picks the folder, so Settings can't switch it."""
    return "LIFEOS_DATA_DIR" in os.environ


def chosen():
    """'personal' or 'test': the folder chosen in Settings (personal until then)."""
    try:
        which = CHOICE_FILE.read_text().strip()
    except FileNotFoundError:
        return "personal"
    return which if which in FOLDERS else "personal"


def current():
    """'personal' or 'test' for the folder in use; None for a LIFEOS_DATA_DIR one."""
    for which, folder in FOLDERS.items():
        if db.DATA_DIR.resolve() == folder.resolve():
            return which
    return None


def open_folder(folder):
    """Point the app at `folder` and get it ready; returns the database connection.
    A new test database gets mock data, and an out-of-date one is made again.
    Raises if any other database doesn't match the schema."""
    db.use(folder)
    test = db.DATA_DIR.resolve() == FOLDERS["test"].resolve()  # mock data only ever goes here
    new = not db.DB_PATH.exists()
    try:
        conn = db.connect()
    except RuntimeError:
        if not test:
            raise
        shutil.rmtree(db.DATA_DIR)
        new, conn = True, db.connect()
    if new and test:
        mock_data.add_gym(conn)
        mock_data.add_food(conn)
    ai.write_missing_prompts()  # AI Prompts/: the instructions sent to the AI
    datadoc.write(conn)  # README.md: what's in the data folder, always current
    db.backup(conn, folders=[journal.folder(), templates.folder("Gym").parent, ai.prompts_folder()])
    todo.purge_deleted(conn)
    return conn


def start():
    """Open the folder to use at launch. If your personal folder can't be opened
    (its database no longer matches the schema), the test folder opens instead
    and Settings says why."""
    global error
    if fixed():
        return open_folder(db.DATA_DIR)
    which = chosen()
    try:
        return open_folder(FOLDERS[which])
    except RuntimeError as err:  # only your own folder can fail: test data is made again
        error = f"Your personal folder couldn't be opened, so this is the test folder. {err}"
        return open_folder(FOLDERS["test"])


def switch(conn, which):
    """Open the `which` folder, close `conn` and remember the choice; returns the
    new connection. If that folder can't be opened, the app stays on the old
    one (`conn` still works) and the reason is raised."""
    global error
    if fixed():
        raise ValueError("The data folder is set by LIFEOS_DATA_DIR, so it can't be changed here")
    if which not in FOLDERS:
        raise ValueError(f"No data folder called {which!r}")
    old = db.DATA_DIR
    try:
        new = open_folder(FOLDERS[which])
    except RuntimeError as err:
        db.use(old)  # stay on the old folder, its connection still open
        raise ValueError(str(err)) from None
    conn.close()
    CHOICE_FILE.write_text(which + "\n")
    error = None
    return new


def reset_test(conn):
    """Delete the test folder and start it again with fresh mock data; returns
    the new connection. Only while the test folder is in use."""
    if current() != "test":
        raise ValueError("Switch to the test folder to reset it")
    conn.close()
    shutil.rmtree(FOLDERS["test"])
    return open_folder(FOLDERS["test"])


def status():
    """What Settings shows: the folder in use, both choices and any problem."""
    return {
        "which": current(),
        "path": str(db.DATA_DIR),
        "folders": {which: str(folder) for which, folder in FOLDERS.items()},
        "fixed": fixed(),
        "error": error,
    }
