"""Gym logic. Plain functions: take a database connection, return plain data.

Gym owns its daily log (gym_log: one free-text entry per day, typed here or in
the Overview), the structured sets of each entry (workout_sets), typed in by
hand or extracted by AI, and the exercises library those sets point at.

Workout templates are text files (app/templates.py): the Gym box's + copies
one into the day's text.
"""
import sqlite3

from app import daylog

LOG = "gym_log"


def _clean(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("Name can't be empty")
    return text


# --- Daily log ---

def get_day(conn, day):
    """The day's Gym text ('' if none)."""
    return daylog.get_day(conn, LOG, day)


def save_day(conn, day, body):
    """Save the day's Gym text; returns the entry id (None once emptied)."""
    return daylog.save_day(conn, LOG, day, body)


# --- Exercises library ---
# Sets point at an exercise, so renaming one changes every past set. Names are
# unique ignoring capitals ("bench press" is "Bench press").

def _exercise_named(conn, name):
    return conn.execute("SELECT id, name FROM exercises WHERE name = ? COLLATE NOCASE", (name.strip(),)).fetchone()


def _exercise_id(conn, name):
    """The id of the exercise with this name, adding it to the library if new.
    Call inside the transaction that uses it."""
    row = _exercise_named(conn, name)
    if row:
        return row["id"]
    return conn.execute("INSERT INTO exercises (name) VALUES (?)", (name.strip(),)).lastrowid


def add_exercise(conn, name):
    """Add an exercise before you've done it; return its id."""
    name = _clean(name)
    if _exercise_named(conn, name):
        raise ValueError(f"“{name}” is already an exercise")
    with conn:
        return conn.execute("INSERT INTO exercises (name) VALUES (?)", (name,)).lastrowid


def rename_exercise(conn, exercise_id, name):
    """Rename an exercise everywhere. A name another exercise already has is refused."""
    name = _clean(name)
    other = _exercise_named(conn, name)
    if other and other["id"] != exercise_id:
        raise ValueError(f"“{other['name']}” is already an exercise")
    with conn:
        conn.execute("UPDATE exercises SET name = ? WHERE id = ?", (name, exercise_id))


def delete_exercise(conn, exercise_id):
    """Delete an exercise with no sets (past sets need their exercise)."""
    try:
        with conn:
            conn.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
    except sqlite3.IntegrityError:
        raise ValueError("This exercise has sets logged, so it can't be deleted") from None


# --- Structured sets (entered by hand, or by AI analysis of workout entries) ---

# A set as the app sees it: the exercise's name comes from the library.
# Weights are kg; None is bodyweight.
SET_COLUMNS = "x.name AS exercise, s.exercise_id, s.set_no, s.reps, s.weight, s.note"
SETS = "workout_sets s JOIN exercises x ON x.id = s.exercise_id"


def _number(value, name, whole=False):
    """None/'' -> None; otherwise a non-negative number (or refuse)."""
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if n < 0 or (whole and n != int(n)):
        raise ValueError(f"{name} must be a {'whole ' if whole else ''}number of 0 or more")
    return int(n) if whole else n


def save_sets(conn, entry_id, sets):
    """Replace an entry's structured sets and mark them as matching its current text.
    Each set names its exercise; new names are added to the library. Sets are
    numbered per exercise in the order given. Saving no sets clears the entry
    back to 'not analysed'."""
    if daylog.get_entry(conn, LOG, entry_id) is None:
        raise ValueError("That entry no longer exists")
    rows, counts = [], {}
    for s in sets:
        exercise = (s.get("exercise") or "").strip()
        if not exercise:
            raise ValueError("Every set needs an exercise")
        reps = _number(s.get("reps"), "Reps", whole=True)
        weight = _number(s.get("weight"), "Weight")  # None = bodyweight
        if reps is None:
            raise ValueError(f"{exercise}: each set needs reps")
        counts[exercise.lower()] = counts.get(exercise.lower(), 0) + 1
        rows.append((exercise, counts[exercise.lower()], reps, weight, (s.get("note") or "").strip()))
    with conn:  # checked everything first, so a bad set adds no exercises
        conn.execute("DELETE FROM workout_sets WHERE entry_id = ?", (entry_id,))
        conn.executemany(
            "INSERT INTO workout_sets (entry_id, exercise_id, set_no, reps, weight, note) VALUES (?, ?, ?, ?, ?, ?)",
            [(entry_id, _exercise_id(conn, r[0]), *r[1:]) for r in rows])
        daylog.set_analysed(conn, LOG, entry_id, analysed=bool(rows))


def top_set(sets):
    """The heaviest set (most reps breaking a tie); bodyweight counts as 0 kg."""
    return max((s for s in sets if s["reps"]), key=lambda s: (s["weight"] or 0.0, s["reps"]), default=None)


def _sets_by_entry(conn, entry_ids, exercise_id=None):
    if not entry_ids:
        return {}
    sql = f"SELECT s.entry_id, {SET_COLUMNS} FROM {SETS} WHERE s.entry_id IN ({','.join('?' * len(entry_ids))})"
    params = list(entry_ids)
    if exercise_id is not None:
        sql += " AND s.exercise_id = ?"
        params.append(exercise_id)
    by_entry = {}
    for row in conn.execute(sql + " ORDER BY s.entry_id, s.id", params):
        s = dict(row)
        by_entry.setdefault(s.pop("entry_id"), []).append(s)
    return by_entry


def _group_by_exercise(sets):
    groups = {}
    for s in sets:
        groups.setdefault(s["exercise_id"], []).append(s)
    return [{"exercise_id": exercise_id, "exercise": rows[0]["exercise"], "sets": rows}
            for exercise_id, rows in groups.items()]


def get_sessions(conn):
    """Every day in the Gym log, newest first, with its structured data.
    status: 'analysed', 'changed' (text edited since analysis) or 'not_analysed'."""
    entries = daylog.get_all(conn, LOG)
    sets = _sets_by_entry(conn, [e["id"] for e in entries])
    for e in entries:
        e["exercises"] = _group_by_exercise(sets.get(e["id"], []))
    return entries


def get_exercises(conn):
    """The whole library: exercises you've done, most recently done first, with
    their session count, last day and best set; then ones not done yet."""
    groups = {row["id"]: {"id": row["id"], "exercise": row["name"], "entries": set(), "last_day": None, "sets": []}
              for row in conn.execute("SELECT id, name FROM exercises")}
    for row in conn.execute(f"SELECT s.entry_id, e.day, {SET_COLUMNS} FROM {SETS} JOIN gym_log e ON e.id = s.entry_id ORDER BY e.day, s.id"):
        s = dict(row)
        g = groups[s["exercise_id"]]
        g["entries"].add(s.pop("entry_id"))
        g["last_day"] = s.pop("day")
        g["sets"].append(s)
    exercises = [
        {"id": g["id"], "exercise": g["exercise"], "sessions": len(g["entries"]), "last_day": g["last_day"], "top": top_set(g["sets"])}
        for g in groups.values()
    ]
    done = sorted((x for x in exercises if x["sessions"]), key=lambda x: (x["last_day"], x["exercise"].lower()), reverse=True)
    not_done = sorted((x for x in exercises if not x["sessions"]), key=lambda x: x["exercise"].lower())
    return done + not_done
