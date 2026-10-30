"""Food logic: the foods library and each day's items (copies of the numbers)."""
import pytest

from app.tabs import food, gym


def food_entry(conn, body="Breakfast", day="2026-10-08"):
    return food.save_day(conn, day, body)


def egg(**extra):
    return {"name": "Egg", "amount": 2, "unit": "egg", "calories": 140, "protein": 12, "carbs": 1, "fat": 10, **extra}


def test_food_defaults_and_updates(conn):
    oats = food.create_food(conn, "  Oats ")
    assert food.get_foods(conn) == [{"id": oats, "name": "Oats", "unit": "g", "per_amount": 100,
                                     "calories": 0, "protein": 0, "carbs": 0, "fat": 0}]
    food.update_food(conn, oats, {"calories": "389", "protein": 17})
    assert food.get_foods(conn)[0]["calories"] == 389


@pytest.mark.parametrize("fields", [{"name": " "}, {"unit": ""}, {"per_amount": 0}, {"calories": -1}, {"fat": "lots"}])
def test_food_refuses_bad_values(conn, fields):
    oats = food.create_food(conn, "Oats")
    with pytest.raises(ValueError):
        food.update_food(conn, oats, fields)


def test_food_names_are_unique(conn):
    oats = food.create_food(conn, "Oats")
    rice = food.create_food(conn, "Rice")
    with pytest.raises(ValueError):
        food.create_food(conn, "OATS")
    with pytest.raises(ValueError):
        food.update_food(conn, rice, {"name": "oats"})
    food.update_food(conn, oats, {"name": "Oats"})  # keeping your own name is fine


def test_for_amount():
    oil = {"per_amount": 100, "calories": 800, "protein": 0, "carbs": 0, "fat": 90}
    assert food.for_amount(oil, 15) == {"calories": 120, "protein": 0, "carbs": 0, "fat": 13.5}


def test_diary_items_and_totals(conn):
    e = food_entry(conn, "2 eggs and a pizza")
    food.save_items(conn, e, [egg(), {"name": "Pizza", "amount": 3, "unit": "slice", "calories": 855, "protein": 36,
                                      "carbs": 99, "fat": 33}])
    [entry] = food.get_diary(conn)
    assert entry["status"] == "analysed"
    assert [(i["name"], i["amount"], i["unit"], i["calories"]) for i in entry["items"]] == [
        ("Egg", 2, "egg", 140), ("Pizza", 3, "slice", 855)]
    assert entry["total"] == {"calories": 995, "protein": 48, "carbs": 100, "fat": 43}


def test_items_keep_their_numbers_when_the_library_changes(conn):
    egg_id = food.create_food(conn, "Egg")
    e = food_entry(conn)
    food.save_items(conn, e, [egg()])
    food.update_food(conn, egg_id, {"calories": 999})
    food.delete_food(conn, egg_id)
    assert food.get_diary(conn)[0]["total"]["calories"] == 140


def test_amount_and_unit_are_optional(conn):
    e = food_entry(conn)
    food.save_items(conn, e, [{"name": "Coffee", "amount": "", "calories": 5}])
    [item] = food.get_diary(conn)[0]["items"]
    assert (item["amount"], item["unit"], item["protein"]) == (None, "", 0)


def test_diary_newest_first_and_only_food(conn):
    food_entry(conn, "Breakfast", "2026-10-07")
    food_entry(conn, "Lunch", "2026-10-08")
    gym.save_day(conn, "2026-10-09", "Squat")  # Gym's, not Food's
    assert [(e["day"], e["body"]) for e in food.get_diary(conn)] == [("2026-10-08", "Lunch"), ("2026-10-07", "Breakfast")]


@pytest.mark.parametrize("bad", [egg(name=" "), egg(amount=-1), egg(calories="lots"), egg(fat=-2)])
def test_save_items_refuses_bad_items_and_keeps_old(conn, bad):
    e = food_entry(conn)
    food.save_items(conn, e, [egg()])
    with pytest.raises(ValueError):
        food.save_items(conn, e, [egg(calories=70), bad])
    assert food.get_diary(conn)[0]["total"]["calories"] == 140


def test_save_items_needs_an_entry_and_empty_clears(conn):
    with pytest.raises(ValueError):
        food.save_items(conn, 999, [])
    e = food_entry(conn)
    food.save_items(conn, e, [egg()])
    food.save_items(conn, e, [])
    assert food.get_diary(conn)[0]["status"] == "not_analysed"


def test_deleting_entry_removes_items(conn):
    e = food_entry(conn)
    food.save_items(conn, e, [egg()])
    with conn:
        conn.execute("DELETE FROM food_log WHERE id = ?", (e,))
    assert conn.execute("SELECT COUNT(*) FROM food_items").fetchone()[0] == 0
