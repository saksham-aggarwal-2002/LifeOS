"""Journal: one plain text file per day in LifeOS_data/Journal Entries, not the database.

    Journal Entries/2026-10-27.txt

    Tuesday, 27 October 2026

    The day's text...

The date line at the top is written by the app and left out when reading, so
the files read well on their own (and can be opened or edited in any editor).
"""
import os
from datetime import date

from app import db

FOLDER_NAME = "Journal Entries"


def folder():
    """LifeOS_data/Journal Entries (follows db.DATA_DIR, so tests use a temp folder)."""
    return db.DATA_DIR / FOLDER_NAME


def _path(day):
    return folder() / f"{date.fromisoformat(day).isoformat()}.txt"


def heading(day):
    d = date.fromisoformat(day)
    return f"{d:%A}, {d.day} {d:%B %Y}"


def read(day):
    """A day's text, or '' when there's no file."""
    path = _path(day)
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[0].strip() == heading(day):  # drop the date line and the blank after it
        lines = lines[2:] if len(lines) > 1 and not lines[1].strip() else lines[1:]
    return "\n".join(lines)


def write(day, body):
    """Save a day's text; empty text deletes the day's file."""
    path = _path(day)
    if not (body or "").strip():
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(f"{heading(day)}\n\n{body}", encoding="utf-8")
    os.replace(temp, path)  # all-or-nothing: a crash never leaves half a file


def get_day(day):
    """The day's Journal text ('' if none). Same shape as Gym's and Food's."""
    return read(day)


def save_day(day, body):
    write(day, body)


def get_all():
    """Every day with a journal file, newest first: [{day, body}]."""
    days = []
    for path in folder().glob("*.txt") if folder().exists() else []:
        try:
            day = date.fromisoformat(path.stem).isoformat()
        except ValueError:
            continue  # not one of ours
        body = read(day)
        if body.strip():
            days.append({"day": day, "body": body})
    return sorted(days, key=lambda d: d["day"], reverse=True)

