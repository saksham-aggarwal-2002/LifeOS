"""To Do logic, tested through the same functions the UI calls."""
from datetime import date, timedelta

import pytest

from app.tabs import todo

TODAY = "2026-10-25"


def day(offset):
    """A date relative to today, as the 'YYYY-MM-DD' strings the app uses."""
    return (date.today() + timedelta(days=offset)).isoformat()


def titles(tasks):
    return [t["title"] for t in tasks]


# --- Lists ---

def test_starts_with_one_list_called_tasks(conn):
    assert [l["name"] for l in todo.get_lists(conn)] == ["Tasks"]


def test_create_rename_and_delete_a_list(conn):
    lid = todo.create_list(conn, "  Groceries  ")
    assert todo.get_lists(conn)[-1] == {"id": lid, "name": "Groceries", "open_count": 0}
    todo.rename_list(conn, lid, "Shopping")
    assert todo.get_lists(conn)[-1]["name"] == "Shopping"
    todo.delete_list(conn, lid)
    assert [l["name"] for l in todo.get_lists(conn)] == ["Tasks"]


@pytest.mark.parametrize("name", ["", "   ", None])
def test_empty_names_are_refused(conn, name):
    with pytest.raises(ValueError):
        todo.create_list(conn, name)
    with pytest.raises(ValueError):
        todo.add_task(conn, 1, name)


def test_last_list_cannot_be_deleted(conn):
    with pytest.raises(ValueError):
        todo.delete_list(conn, 1)


def test_deleting_a_list_deletes_its_tasks(conn):
    lid = todo.create_list(conn, "Temp")
    todo.add_task(conn, lid, "goes too")
    todo.delete_list(conn, lid)
    assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_open_count_ignores_completed_and_deleted(conn):
    todo.add_task(conn, 1, "open")
    todo.toggle_task(conn, todo.add_task(conn, 1, "done"))
    todo.delete_task(conn, todo.add_task(conn, 1, "deleted"))
    assert todo.get_lists(conn)[0]["open_count"] == 1


def test_reorder_lists(conn):
    a = todo.create_list(conn, "A")
    b = todo.create_list(conn, "B")
    todo.reorder_lists(conn, [b, 1, a])
    assert [l["name"] for l in todo.get_lists(conn)] == ["B", "Tasks", "A"]


@pytest.mark.parametrize("bad", [[1], [1, 1, 2], [1, 2, 99]])
def test_reorder_must_include_every_list_once(conn, bad):
    todo.create_list(conn, "A")  # id 2
    with pytest.raises(ValueError):
        todo.reorder_lists(conn, bad)


# --- Tasks ---

def test_add_and_rename_a_task(conn):
    tid = todo.add_task(conn, 1, " Milk ")
    todo.rename_task(conn, tid, "Oat milk")
    assert titles(todo.get_tasks(conn, 1)) == ["Oat milk"]


def test_add_task_without_list_goes_to_first_list(conn):
    lid = todo.create_list(conn, "Top")
    todo.reorder_lists(conn, [lid, 1])
    todo.add_task(conn, None, "from My Day")
    assert titles(todo.get_tasks(conn, lid)) == ["from My Day"]


def test_toggle_records_and_clears_completion_time(conn):
    tid = todo.add_task(conn, 1, "x")
    todo.toggle_task(conn, tid)
    task = todo.get_tasks(conn, 1)[0]
    assert task["completed"] == 1 and task["completed_at"]
    todo.toggle_task(conn, tid)
    task = todo.get_tasks(conn, 1)[0]
    assert task["completed"] == 0 and task["completed_at"] is None


def test_open_tasks_oldest_first_then_completed_newest_first(conn):
    a, b, c, d = (todo.add_task(conn, 1, t) for t in "ABCD")
    todo.toggle_task(conn, a)
    todo.toggle_task(conn, c)
    assert titles(todo.get_tasks(conn, 1)) == ["B", "D", "C", "A"]


def test_do_date_set_clear_and_validate(conn):
    tid = todo.add_task(conn, 1, "x")
    todo.set_do_date(conn, tid, "2026-11-01")
    assert todo.get_tasks(conn, 1)[0]["do_date"] == "2026-11-01"
    todo.set_do_date(conn, tid, None)
    assert todo.get_tasks(conn, 1)[0]["do_date"] is None
    for bad in ["2026-13-01", "tomorrow", "01/11/2026"]:
        with pytest.raises(ValueError):
            todo.set_do_date(conn, tid, bad)


# --- My Day ---

def test_my_day_shows_tasks_whose_do_date_has_arrived(conn):
    lid = todo.create_list(conn, "Groceries")
    todo.add_task(conn, lid, "overdue", "2026-10-20")
    todo.add_task(conn, 1, "today", TODAY)
    todo.add_task(conn, 1, "tomorrow", "2026-10-26")
    todo.add_task(conn, 1, "no date")
    my_day = todo.get_my_day(conn, today=TODAY)
    assert titles(my_day) == ["overdue", "today"]
    assert my_day[0]["list_name"] == "Groceries"


def test_tomorrows_task_appears_tomorrow(conn):
    todo.add_task(conn, 1, "tomorrow", "2026-10-26")
    assert titles(todo.get_my_day(conn, today="2026-10-26")) == ["tomorrow"]


def test_my_day_keeps_tasks_completed_today_only(conn):
    done_today = todo.add_task(conn, 1, "done today", day(0))
    done_before = todo.add_task(conn, 1, "done before", day(-3))
    todo.toggle_task(conn, done_today)
    todo.toggle_task(conn, done_before)
    conn.execute("UPDATE tasks SET completed_at = '2020-01-01 09:00:00' WHERE id = ?", (done_before,))
    conn.commit()
    assert titles(todo.get_my_day(conn)) == ["done today"]


# --- Calendar ---

def test_calendar_returns_tasks_in_range_inclusive(conn):
    for d in ["2026-10-18", "2026-10-19", "2026-10-22", "2026-10-25", "2026-10-26"]:
        todo.add_task(conn, 1, d, d)
    week = todo.get_calendar(conn, "2026-10-19", "2026-10-25")
    assert titles(week) == ["2026-10-19", "2026-10-22", "2026-10-25"]


def test_unscheduled_is_open_tasks_without_a_date(conn):
    lid = todo.create_list(conn, "Groceries")
    todo.add_task(conn, lid, "bread")
    todo.add_task(conn, 1, "call bank")
    todo.add_task(conn, 1, "dated", TODAY)
    todo.toggle_task(conn, todo.add_task(conn, 1, "done"))
    assert titles(todo.get_unscheduled(conn)) == ["call bank", "bread"]  # list order, then age


# --- Recently deleted ---

def test_deleted_task_disappears_everywhere(conn):
    tid = todo.add_task(conn, 1, "gone", TODAY)
    todo.delete_task(conn, tid)
    assert todo.get_tasks(conn, 1) == []
    assert todo.get_my_day(conn, today=TODAY) == []
    assert todo.get_calendar(conn, TODAY, TODAY) == []
    assert titles(todo.get_deleted(conn)) == ["gone"]


def test_restore_brings_a_task_back_as_it_was(conn):
    tid = todo.add_task(conn, 1, "back", TODAY)
    todo.toggle_task(conn, tid)
    todo.delete_task(conn, tid)
    todo.restore_task(conn, tid)
    task = todo.get_tasks(conn, 1)[0]
    assert (task["title"], task["do_date"], task["completed"]) == ("back", TODAY, 1)
    assert todo.get_deleted(conn) == []


def test_purge_removes_only_old_deleted_tasks(conn):
    old = todo.add_task(conn, 1, "old")
    recent = todo.add_task(conn, 1, "recent")
    todo.add_task(conn, 1, "not deleted")
    todo.delete_task(conn, old)
    todo.delete_task(conn, recent)
    conn.execute("UPDATE tasks SET deleted_at = datetime('now', 'localtime', '-31 days') WHERE id = ?", (old,))
    conn.commit()
    todo.purge_deleted(conn)
    assert titles(todo.get_deleted(conn)) == ["recent"]
    assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 2
