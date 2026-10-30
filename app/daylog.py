"""A tab's daily log: one free-text entry per day, in the tab's own table
(gym_log, food_log). Gym and Food build on these; the Overview reaches them
through those tabs, the way it reaches To Do's tasks.

Structured data (Gym sets, Food items) points at an entry. analysed_hash
remembers which text that data was saved for, to spot later edits."""
import hashlib
from datetime import date

# table -> the table of structured data pointing at its entries
TABLES = {"gym_log": "workout_sets", "food_log": "food_items"}


def _table(table):
    if table not in TABLES:  # table names can't be ? parameters, so only known ones
        raise ValueError(f"Unknown log: {table!r}")
    return table


def _check_date(value):
    return date.fromisoformat(value).isoformat()


def entry_hash(body):
    """Fingerprint of an entry's text."""
    return hashlib.sha256(body.encode()).hexdigest()


def analysis_status(analysed_hash, body):
    """'not_analysed', 'analysed', or 'changed' (text edited since)."""
    if analysed_hash is None:
        return "not_analysed"
    return "analysed" if analysed_hash == entry_hash(body) else "changed"


def get_entry(conn, table, entry_id):
    """{id, day, body, analysed_hash}, or None."""
    row = conn.execute(f"SELECT id, day, body, analysed_hash FROM {_table(table)} WHERE id = ?", (entry_id,)).fetchone()
    return dict(row) if row else None


def get_day(conn, table, day):
    """A day's entry text, or '' when there's none."""
    row = conn.execute(f"SELECT body FROM {_table(table)} WHERE day = ?", (_check_date(day),)).fetchone()
    return row["body"] if row else ""


def get_all(conn, table):
    """Every entry, newest day first, each with its analysis status."""
    rows = [dict(r) for r in conn.execute(f"SELECT id, day, body, analysed_hash FROM {_table(table)} ORDER BY day DESC")]
    for r in rows:
        r["status"] = analysis_status(r.pop("analysed_hash"), r["body"])
    return rows


def save_day(conn, table, day, body):
    """Save a day's text: creates the entry on first text, updates it after.
    Emptying it removes the entry, unless it has structured data, which stays
    until you clear it. Returns the entry id, or None when there's no entry."""
    day, body = _check_date(day), body or ""
    data = TABLES[_table(table)]
    row = conn.execute(f"SELECT id FROM {table} WHERE day = ?", (day,)).fetchone()
    with conn:
        if row is None:
            if not body.strip():
                return None
            return conn.execute(f"INSERT INTO {table} (day, body) VALUES (?, ?)", (day, body)).lastrowid
        has_data = conn.execute(f"SELECT EXISTS (SELECT 1 FROM {data} WHERE entry_id = ?)", (row["id"],)).fetchone()[0]
        if not body.strip() and not has_data:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (row["id"],))
            return None
        conn.execute(f"UPDATE {table} SET body = ? WHERE id = ?", (body, row["id"]))
        return row["id"]


def set_analysed(conn, table, entry_id, analysed=True):
    """Record that the entry's current text has (or hasn't) got matching
    structured data. Call inside the transaction that saved that data."""
    entry = get_entry(conn, table, entry_id)
    conn.execute(f"UPDATE {table} SET analysed_hash = ? WHERE id = ?",
                 (entry_hash(entry["body"]) if analysed else None, entry_id))
