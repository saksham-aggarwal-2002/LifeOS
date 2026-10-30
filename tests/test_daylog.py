"""Each tab's daily log (Gym's, Food's): one entry per day, in its own table."""
import sqlite3

import pytest

from app.tabs import food, gym

DAY = "2026-10-25"


def test_save_day_creates_updates_and_removes(conn):
    eid = food.save_day(conn, DAY, "Oats")
    assert food.save_day(conn, DAY, "Oats, banana") == eid   # same day, same entry
    assert food.get_day(conn, DAY) == "Oats, banana"
    assert food.save_day(conn, DAY, "  ") is None             # emptied: gone
    assert food.get_day(conn, DAY) == ""
    assert gym.save_day(conn, DAY, "") is None                # nothing typed: nothing made


def test_tabs_keep_their_own_days(conn):
    gym.save_day(conn, DAY, "Squat")
    food.save_day(conn, DAY, "Oats")
    assert (gym.get_day(conn, DAY), food.get_day(conn, DAY)) == ("Squat", "Oats")
    assert [s["body"] for s in gym.get_sessions(conn)] == ["Squat"]
    assert [e["body"] for e in food.get_diary(conn)] == ["Oats"]


def test_emptied_day_keeps_entry_with_structured_data(conn):
    eid = gym.save_day(conn, DAY, "Squat 5x5 @ 100")
    gym.save_sets(conn, eid, [{"exercise": "Squat", "reps": 5, "weight": 100}])
    assert gym.save_day(conn, DAY, "") == eid
    assert gym.get_sessions(conn)[0]["exercises"][0]["exercise"] == "Squat"


def test_one_entry_per_day_enforced_by_the_database(conn):
    gym.save_day(conn, DAY, "Squat")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO gym_log (day) VALUES (?)", (DAY,))


def test_bad_day_refused(conn):
    with pytest.raises(ValueError):
        food.save_day(conn, "25/10/2026", "Oats")
