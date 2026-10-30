"""Overview (internally "log"): one day from every tab in one place. It keeps
no data of its own: each tab owns its day (To Do's tasks, Gym's and Food's
text, the Journal file, Body's weight), and the Overview reads it through that
tab's functions. Saving goes straight to the tab too (gym.save_day, ...)."""
from datetime import date

from app.tabs import body, food, gym, journal, todo


def get_day(conn, day, today=None):
    """Everything the Overview shows for a day."""
    return {
        "tasks": get_day_tasks(conn, day, today),
        "gym": gym.get_day(conn, day),
        "food": food.get_day(conn, day),
        "journal": journal.get_day(day),
        "weight": body.get_weight(conn, day),
    }


def get_day_tasks(conn, day, today=None):
    """The To Do tasks for a day: My Day for today (overdue included);
    for any other day, the tasks whose do date is that day."""
    today = today or date.today().isoformat()
    day = date.fromisoformat(day).isoformat()
    if day == today:
        return todo.get_my_day(conn, today=today)
    return todo.get_calendar(conn, day, day)
