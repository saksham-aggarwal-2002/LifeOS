"""The Overview: a day from every tab, read through that tab's functions."""
from app.tabs import body, food, gym, journal, log, todo

DAY = "2026-10-25"


def test_day_gathers_every_tab(conn):
    todo.add_task(conn, 1, "Call home", DAY)
    gym.save_day(conn, DAY, "Squat")
    food.save_day(conn, DAY, "Oats")
    journal.save_day(DAY, "Good day")
    body.save_weight(conn, DAY, 80.2)
    day = log.get_day(conn, DAY, today=DAY)
    assert [t["title"] for t in day.pop("tasks")] == ["Call home"]
    assert day == {"gym": "Squat", "food": "Oats", "journal": "Good day", "weight": 80.2}


def test_empty_day(conn):
    assert log.get_day(conn, DAY, today=DAY) == {"tasks": [], "gym": "", "food": "", "journal": "", "weight": None}


def test_day_tasks_today_is_my_day_other_days_are_that_date(conn):
    todo.add_task(conn, 1, "overdue", "2026-10-20")
    todo.add_task(conn, 1, "today", DAY)
    todo.add_task(conn, 1, "tomorrow", "2026-10-26")
    titles = lambda tasks: [t["title"] for t in tasks]
    assert titles(log.get_day_tasks(conn, DAY, today=DAY)) == ["overdue", "today"]
    assert titles(log.get_day_tasks(conn, "2026-10-26", today=DAY)) == ["tomorrow"]
    assert titles(log.get_day_tasks(conn, "2026-10-20", today=DAY)) == ["overdue"]


def test_each_tab_saves_and_reads_its_own_day_through_the_bridge(conn):
    # The tabs and the Overview call these same methods, so both show the same day.
    from app.api import Api
    api = Api(conn)
    api.gym_save_day(DAY, "Squat")
    api.food_save_day(DAY, "Oats")
    api.journal_save_day(DAY, "Good day")
    api.body_save_weight(DAY, "80.2")
    assert (api.gym_get_day(DAY), api.food_get_day(DAY), api.journal_get_day(DAY), api.body_get_weight(DAY)) == (
        "Squat", "Oats", "Good day", 80.2)
    day = api.log_get_day(DAY)
    assert (day["gym"], day["food"], day["journal"], day["weight"]) == ("Squat", "Oats", "Good day", 80.2)
