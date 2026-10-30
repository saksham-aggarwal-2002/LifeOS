"""Food logic. Plain functions: take a database connection, return plain data.

Food owns its daily log (food_log: one free-text entry per day, typed here or
in the Overview), a library of foods (macros per an amount of a unit, e.g. per
100 g or per 1 egg), and each day's items: everything eaten, as its own name,
amount and numbers, typed in by hand or extracted by AI. Items are copies, not
links: correcting a food in the library never changes past days.

Recipes are templates (app/templates.py): text you drop into the day's box.
"""
import sqlite3

from app import daylog

LOG = "food_log"

MACROS = ("calories", "protein", "carbs", "fat")
FOOD_COLUMNS = "id, name, unit, per_amount, calories, protein, carbs, fat"
ITEM_COLUMNS = "name, amount, unit, calories, protein, carbs, fat"


# --- Daily log ---

def get_day(conn, day):
    """The day's Food text ('' if none)."""
    return daylog.get_day(conn, LOG, day)


def save_day(conn, day, body):
    """Save the day's Food text; returns the entry id (None once emptied)."""
    return daylog.save_day(conn, LOG, day, body)


def _clean(text, what="Name"):
    text = (text or "").strip()
    if not text:
        raise ValueError(f"{what} can't be empty")
    return text


def _number(value, what, positive=False):
    """A number >= 0 (or > 0 when `positive`); refuse anything else."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number") from None
    if n < 0 or (positive and n == 0):
        raise ValueError(f"{what} must be {'more than' if positive else 'at least'} 0")
    return n


def _rounded(macros):
    return {m: round(macros[m], 1) for m in MACROS}


def for_amount(food, amount):
    """A food's macros for `amount` of its unit."""
    return _rounded({m: food[m] * amount / food["per_amount"] for m in MACROS})


# --- Foods ---

def get_foods(conn):
    rows = conn.execute(f"SELECT {FOOD_COLUMNS} FROM foods ORDER BY name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def create_food(conn, name):
    """Add a food (per 100 g, all zero until edited); return its id."""
    name = _clean(name)
    try:
        with conn:
            return conn.execute("INSERT INTO foods (name) VALUES (?)", (name,)).lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"There's already a food called {name!r}") from None


def update_food(conn, food_id, fields):
    """Change some of a food's name, unit, per_amount and macros."""
    values = {}
    if "name" in fields:
        values["name"] = _clean(fields["name"])
    if "unit" in fields:
        values["unit"] = _clean(fields["unit"], "Unit")
    if "per_amount" in fields:
        values["per_amount"] = _number(fields["per_amount"], "Amount", positive=True)
    for m in MACROS:
        if m in fields:
            values[m] = _number(fields[m], m.capitalize())
    if values:
        try:
            with conn:
                conn.execute(f"UPDATE foods SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
                             (*values.values(), food_id))
        except sqlite3.IntegrityError:
            raise ValueError(f"There's already a food called {values['name']!r}") from None


def delete_food(conn, food_id):
    """Delete a food. Days it was eaten on keep their numbers (they're copies)."""
    with conn:
        conn.execute("DELETE FROM foods WHERE id = ?", (food_id,))


# --- Diary items ---

def _clean_item(item):
    """Check one item: a name, an optional amount + unit, and its macros."""
    amount = item.get("amount")
    return {
        "name": _clean(item.get("name")),
        "amount": None if amount in (None, "") else _number(amount, "Amount"),
        "unit": (item.get("unit") or "").strip(),
        **{m: _number(item.get(m) or 0, m.capitalize()) for m in MACROS},
    }


def save_items(conn, entry_id, items):
    """Replace a food entry's items and mark them as matching its current text.
    Saving no items clears the entry back to 'not analysed'."""
    if daylog.get_entry(conn, LOG, entry_id) is None:
        raise ValueError("That food entry no longer exists")
    clean = [_clean_item(item) for item in items]
    with conn:
        conn.execute("DELETE FROM food_items WHERE entry_id = ?", (entry_id,))
        conn.executemany(
            f"INSERT INTO food_items (entry_id, position, {ITEM_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(entry_id, position, *item.values()) for position, item in enumerate(clean)],
        )
        daylog.set_analysed(conn, LOG, entry_id, analysed=bool(clean))


def _total(items):
    return _rounded({m: sum(item[m] for item in items) for m in MACROS})


def get_diary(conn):
    """Every day in the Food log (newest first), each with its items and total:
    [{id, day, body, status, items, total}]."""
    entries = daylog.get_all(conn, LOG)
    by_entry = {}
    for row in conn.execute(f"SELECT entry_id, {ITEM_COLUMNS} FROM food_items ORDER BY entry_id, position"):
        item = dict(row)
        by_entry.setdefault(item.pop("entry_id"), []).append(item)
    for e in entries:
        e["items"] = by_entry.get(e["id"], [])
        e["total"] = _total(e["items"])
    return entries
