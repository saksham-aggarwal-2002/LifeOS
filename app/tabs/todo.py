"""To Do logic. Plain functions: take a database connection, return plain data.

Dates are 'YYYY-MM-DD' strings in your local time zone.
"""
from datetime import date

KEEP_DELETED_DAYS = 30
NOW = "strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')"

TASK_COLUMNS = (
    "tasks.id, tasks.list_id, tasks.title, tasks.completed, tasks.completed_at,"
    " tasks.do_date, tasks.created_at, tasks.deleted_at"
)
# Open tasks first (oldest at top), then completed ones (most recent at top).
TASK_ORDER = (
    "tasks.completed,"
    " CASE WHEN tasks.completed THEN tasks.completed_at END DESC,"
    " CASE WHEN tasks.completed THEN tasks.id END DESC,"
    " tasks.created_at, tasks.id"
)


def _today():
    return date.today().isoformat()


def _clean(text):
    """Trim whitespace; refuse empty names/titles."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Text can't be empty")
    return text


# --- Lists ---

def get_lists(conn):
    """All lists in sidebar order, each with its number of open tasks."""
    rows = conn.execute("""
        SELECT lists.id, lists.name, COUNT(tasks.id) AS open_count
        FROM lists
        LEFT JOIN tasks ON tasks.list_id = lists.id
            AND tasks.completed = 0 AND tasks.deleted_at IS NULL
        GROUP BY lists.id
        ORDER BY lists.position, lists.id
    """).fetchall()
    return [dict(row) for row in rows]


def create_list(conn, name):
    """Add a list at the bottom of the sidebar; return its id."""
    with conn:  # `with conn` = commit on success, roll back on error
        cur = conn.execute(
            "INSERT INTO lists (name, position)"
            " VALUES (?, (SELECT COALESCE(MAX(position), 0) + 1 FROM lists))",
            (_clean(name),),
        )
    return cur.lastrowid


def rename_list(conn, list_id, name):
    with conn:
        conn.execute("UPDATE lists SET name = ? WHERE id = ?", (_clean(name), list_id))


def reorder_lists(conn, list_ids):
    """Save a new sidebar order. `list_ids` must contain every list exactly once."""
    existing = {row[0] for row in conn.execute("SELECT id FROM lists")}
    if sorted(list_ids) != sorted(existing):
        raise ValueError("Reorder must include every list exactly once")
    with conn:
        conn.executemany(
            "UPDATE lists SET position = ? WHERE id = ?",
            [(position, list_id) for position, list_id in enumerate(list_ids)],
        )


def delete_list(conn, list_id):
    """Delete a list and all its tasks. The last remaining list can't be deleted."""
    if conn.execute("SELECT COUNT(*) FROM lists").fetchone()[0] <= 1:
        raise ValueError("You need at least one list")
    with conn:
        conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))


# --- Tasks ---

def get_tasks(conn, list_id):
    """Tasks in a list."""
    rows = conn.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks"
        f" WHERE list_id = ? AND deleted_at IS NULL ORDER BY {TASK_ORDER}",
        (list_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_my_day(conn, today=None):
    """Tasks whose do date has arrived: every open one with do_date <= today
    (so overdue tasks stay until done), plus ones completed today.
    Each task includes its list's name."""
    today = today or _today()
    rows = conn.execute(
        f"SELECT {TASK_COLUMNS}, lists.name AS list_name"
        " FROM tasks JOIN lists ON lists.id = tasks.list_id"
        " WHERE tasks.do_date <= ? AND tasks.deleted_at IS NULL"
        "   AND (tasks.completed = 0 OR date(tasks.completed_at) = ?)"
        f" ORDER BY {TASK_ORDER}",
        (today, today),
    ).fetchall()
    return [dict(row) for row in rows]


def get_calendar(conn, start, end):
    """Tasks with a do date between start and end (inclusive), with list names.
    The calendar uses this to fill its grid; moving a task is set_do_date()."""
    rows = conn.execute(
        f"SELECT {TASK_COLUMNS}, lists.name AS list_name"
        " FROM tasks JOIN lists ON lists.id = tasks.list_id"
        " WHERE tasks.do_date BETWEEN ? AND ? AND tasks.deleted_at IS NULL"
        f" ORDER BY tasks.do_date, {TASK_ORDER}",
        (_check_date(start), _check_date(end)),
    ).fetchall()
    return [dict(row) for row in rows]


def get_unscheduled(conn):
    """Open tasks with no do date, grouped by list, for the calendar's side panel."""
    rows = conn.execute(
        f"SELECT {TASK_COLUMNS}, lists.name AS list_name"
        " FROM tasks JOIN lists ON lists.id = tasks.list_id"
        " WHERE tasks.do_date IS NULL AND tasks.completed = 0 AND tasks.deleted_at IS NULL"
        " ORDER BY lists.position, lists.id, tasks.created_at, tasks.id"
    ).fetchall()
    return [dict(row) for row in rows]


def add_task(conn, list_id, title, do_date=None):
    """Add a task. list_id=None puts it in the first list (used by My Day)."""
    if list_id is None:
        list_id = conn.execute(
            "SELECT id FROM lists ORDER BY position, id LIMIT 1"
        ).fetchone()[0]
    do_date = _check_date(do_date)
    with conn:
        cur = conn.execute(
            "INSERT INTO tasks (list_id, title, do_date) VALUES (?, ?, ?)",
            (list_id, _clean(title), do_date),
        )
    return cur.lastrowid


def set_do_date(conn, task_id, do_date):
    """Set (or with None, clear) the day a task should appear in My Day."""
    with conn:
        conn.execute("UPDATE tasks SET do_date = ? WHERE id = ?", (_check_date(do_date), task_id))


def _check_date(value):
    """Accept None/'' (no date) or a real 'YYYY-MM-DD' date; refuse anything else."""
    if not value:
        return None
    return date.fromisoformat(value).isoformat()


def toggle_task(conn, task_id):
    """Flip a task between open and completed, recording when it was completed."""
    with conn:
        conn.execute(
            "UPDATE tasks SET"
            "  completed = 1 - completed,"
            f"  completed_at = CASE WHEN completed = 0 THEN {NOW} END"
            " WHERE id = ?",
            (task_id,),
        )


def rename_task(conn, task_id, title):
    with conn:
        conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (_clean(title), task_id))


# --- Recently deleted ---

def delete_task(conn, task_id):
    """Move a task to Recently deleted (it can be restored)."""
    with conn:
        conn.execute(f"UPDATE tasks SET deleted_at = {NOW} WHERE id = ?", (task_id,))


def restore_task(conn, task_id):
    """Bring a deleted task back to its list, exactly as it was."""
    with conn:
        conn.execute("UPDATE tasks SET deleted_at = NULL WHERE id = ?", (task_id,))


def get_deleted(conn):
    """Deleted tasks, most recently deleted first, with list names."""
    rows = conn.execute(
        f"SELECT {TASK_COLUMNS}, lists.name AS list_name"
        " FROM tasks JOIN lists ON lists.id = tasks.list_id"
        " WHERE tasks.deleted_at IS NOT NULL"
        " ORDER BY tasks.deleted_at DESC, tasks.id DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def purge_deleted(conn, days=KEEP_DELETED_DAYS):
    """Permanently remove tasks deleted more than `days` days ago. Run at startup."""
    with conn:
        conn.execute(
            "DELETE FROM tasks WHERE deleted_at < datetime('now', 'localtime', ?)",
            (f"-{days} days",),
        )
