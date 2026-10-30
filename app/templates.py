"""Templates: text you drop into a day's box with its +, one plain text file
each, like the Journal. Gym's and Food's live in their own folder:

    Templates/Gym/Push.txt
    Templates/Food/Overnight oats.txt

The file name is the template's name; the file is its text. Adding one to a
day copies the text in, so editing the template later never changes past days
(the AI turns the day's text into sets or food items).
"""
import os

from app import db

TABS = ("Gym", "Food")


def folder(tab):
    """LifeOS_data/Templates/<tab> (follows db.DATA_DIR, so tests use a temp folder)."""
    if tab not in TABS:
        raise ValueError(f"No templates for {tab!r}")
    return db.DATA_DIR / "Templates" / tab


def _name(name):
    """A name that works as a file name."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Name can't be empty")
    if "/" in name or ":" in name or name.startswith("."):
        raise ValueError("A name can't contain / or : or start with .")
    return name


def _path(tab, name):
    return folder(tab) / f"{name}.txt"


def _find(tab, name):
    """The file of the template called `name`, ignoring capitals (as macOS does)."""
    for path in folder(tab).glob("*.txt") if folder(tab).exists() else []:
        if path.stem.lower() == name.lower():
            return path
    return None


def get_all(tab):
    """Every template, by name: [{name, body}]."""
    paths = folder(tab).glob("*.txt") if folder(tab).exists() else []
    templates = [{"name": p.stem, "body": p.read_text(encoding="utf-8")} for p in paths]
    return sorted(templates, key=lambda t: t["name"].lower())


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(body or "", encoding="utf-8")
    os.replace(temp, path)  # all-or-nothing: a crash never leaves half a file


def create(tab, name, body=""):
    """Add a template; returns its name."""
    name = _name(name)
    if _find(tab, name):
        raise ValueError(f"There's already a template called {name!r}")
    _write(_path(tab, name), body)
    return name


def save(tab, name, new_name, body):
    """Save a template's text, renaming it if `new_name` differs; returns its name."""
    path = _find(tab, name)
    if path is None:
        raise ValueError(f"No template called {name!r}")
    new_name = _name(new_name)
    other = _find(tab, new_name)
    if other and other != path:
        raise ValueError(f"There's already a template called {new_name!r}")
    _write(path, body)
    if new_name != path.stem:
        os.replace(path, _path(tab, new_name))
    return new_name


def delete(tab, name):
    path = _find(tab, name)
    if path:
        path.unlink()
