"""Extract Structured Data: turn one day's Gym or Food text into Gym sets or Food
items with the AI (app/ai.py), check the result, and save it through the same
functions as editing by hand (gym.save_sets, food.save_items).

The AI says what was done or eaten (estimating foods not in the library);
Python checks ids against the library and does the maths for those. `parse` can be swapped for a fake in tests.
"""
from app import ai, daylog
from app.tabs import food, gym


def _entry(conn, table, entry_id):
    entry = daylog.get_entry(conn, table, entry_id)
    if entry is None:
        raise ValueError("That entry no longer exists")
    return entry["body"]


def extract_workout(conn, entry_id, parse=ai.parse_workout):
    """Replace a Gym entry's sets with ones extracted from its text."""
    body = _entry(conn, gym.LOG, entry_id)
    known = [x["exercise"] for x in gym.get_exercises(conn)]
    sets = parse(body, known)
    gym.save_sets(conn, entry_id, sets)
    if not sets:  # nothing to extract (e.g. just a blank template): still counts as done
        with conn:
            daylog.set_analysed(conn, gym.LOG, entry_id)
    return {"count": len(sets)}


def extract_food(conn, entry_id, parse=ai.parse_food):
    """Replace a Food entry's items with ones extracted from its text."""
    body = _entry(conn, food.LOG, entry_id)
    foods = {f["id"]: f for f in food.get_foods(conn)}
    raw = parse(body, [{k: f[k] for k in ("id", "name", "unit", "per_amount")} for f in foods.values()])
    items = [_food_item(item, foods) for item in raw]
    food.save_items(conn, entry_id, items)
    if not items:
        with conn:
            daylog.set_analysed(conn, food.LOG, entry_id)
    return {"count": len(items)}


def _food_item(item, foods):
    """One AI item -> the item food.save_items stores. A food from the library
    gets its numbers worked out here from the amount; anything else keeps the
    AI's estimate."""
    saved = foods.get(item["food_id"])
    if saved and item["amount"] is not None:
        return {"name": saved["name"], "amount": item["amount"], "unit": saved["unit"],
                **food.for_amount(saved, item["amount"])}
    macros = {m: item[m] for m in food.MACROS}
    if any(v is None for v in macros.values()):
        raise ValueError(f"No numbers for “{item['name']}”")
    return {"name": item["name"] or "Estimate", "amount": item["amount"], "unit": item["unit"], **macros}
