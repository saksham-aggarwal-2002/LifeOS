"""Extract Structured Data with the real AI: checks the prompts in app/ai.py
work on the kinds of text actually typed into the Gym box.

Costs a few API calls and needs the internet, so it only runs when asked:
    LIFEOS_LIVE_AI=1 .venv/bin/python -m pytest tests/test_extract_live.py
"""
import os

import pytest

from app import extract
from app.tabs import food, gym

pytestmark = pytest.mark.skipif(os.environ.get("LIFEOS_LIVE_AI") != "1", reason="set LIFEOS_LIVE_AI=1 to call the real AI")

DAY = "2026-10-26"


def sets_of(conn):
    """{exercise: [(weight, reps), ...]} for the workout on DAY."""
    [session] = [s for s in gym.get_sessions(conn) if s["day"] == DAY]
    return {x["exercise"]: [(s["weight"], s["reps"]) for s in x["sets"]] for x in session["exercises"]}


def test_free_written_workout(conn):
    old = gym.save_day(conn, "2026-10-01", "old")
    gym.save_sets(conn, old, [{"exercise": "Bench press", "reps": 8, "weight": 60}])
    e = gym.save_day(conn, DAY,
                       "Push\nbench 60x8, 62.5x6, 62.5x5\nOHP 3x10 @ 35\ndips 12, 10 (last one slow)\nlateral raises 3x15 @ 8kg")
    extract.extract_workout(conn, e)
    sets = sets_of(conn)
    assert sets["Bench press"] == [(60, 8), (62.5, 6), (62.5, 5)]          # known name reused
    assert sets["Overhead press"] == [(35, 10)] * 3                        # "OHP" spelled out
    assert [s for x, s in sets.items() if "dip" in x.lower()] == [[(None, 12), (None, 10)]]
    assert [s for x, s in sets.items() if "lateral" in x.lower()] == [[(8, 15)] * 3]


def test_filled_in_template(conn):
    e = gym.save_day(conn, DAY,
                       "Push 1\nBench press: 10kg : 5,5,5\nShoulder press: 10kg : 5,7,8\nPush ups: 5,5,5\nPull ups: 6,8,9")
    assert extract.extract_workout(conn, e) == {"count": 12}
    sets = sets_of(conn)
    assert sets["Shoulder press"] == [(10, 5), (10, 7), (10, 8)]
    assert sets["Pull ups"] == [(None, 6), (None, 8), (None, 9)]


def test_one_weight_per_set(conn):
    e = gym.save_day(conn, DAY, "Bicep curl : 5,5, 10 kg : 8,8,8\nLateral raise: 5kg: 5, 5, 5")
    assert extract.extract_workout(conn, e) == {"count": 6}
    sets = sets_of(conn)
    assert sets["Bicep curl"] == [(5, 8), (5, 8), (10, 8)]
    assert sets["Lateral raise"] == [(5, 5)] * 3


def test_blank_template_has_nothing(conn):
    e = gym.save_day(conn, DAY, "Push 1\nBench press: kg :\nShoulder press: kg :\nPush ups:")
    assert extract.extract_workout(conn, e) == {"count": 0}
    assert gym.get_sessions(conn)[0]["status"] == "analysed"


def test_food_matched_to_library(conn):
    egg = food.create_food(conn, "Egg")
    food.update_food(conn, egg, {"unit": "egg", "per_amount": 1, "calories": 72, "protein": 6, "fat": 5})
    bread = food.create_food(conn, "Sourdough bread")
    food.update_food(conn, bread, {"unit": "slice", "per_amount": 1, "calories": 140, "carbs": 27})
    oats = food.create_food(conn, "Oats")
    food.update_food(conn, oats, {"calories": 380, "carbs": 60})
    e = food.save_day(conn, DAY,
                       "Breakfast:\nPorridge\n- Oats 80 g\nLunch:\n2 eggs\n2 pieces of bread\nDinner:\nchicken burrito")
    assert extract.extract_food(conn, e) == {"count": 4}
    by_name = {i["name"]: i for i in food.get_diary(conn)[0]["items"]}
    assert by_name["Oats"]["amount"] == 80 and by_name["Oats"]["calories"] == 304     # recipe line, library numbers
    assert by_name["Egg"]["amount"] == 2 and by_name["Sourdough bread"]["amount"] == 2
    [burrito] = [i for name, i in by_name.items() if "burrito" in name.lower()]
    assert 400 <= burrito["calories"] <= 1400                                          # estimated
