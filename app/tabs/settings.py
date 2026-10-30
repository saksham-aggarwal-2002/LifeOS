"""Settings: information about the app itself, e.g. where your data lives.
Which data folder is in use (and switching it) is app/datafolder.py."""
from app import datadoc, db


def get_readme(conn):
    """LifeOS_data/README.md, rewritten first so it shows the data as it is now."""
    datadoc.write(conn)
    return (db.DATA_DIR / datadoc.FILE_NAME).read_text(encoding="utf-8")
