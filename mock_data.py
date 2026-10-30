"""Mock data, so the tabs have something to show while building the app:
~6 weeks of Push/Pull/Legs workouts and their templates, a small food
library, food templates + 2 weeks of meals.

The test data folder (Settings > Data folder > Test data) gets this when it's
new, and again on "Reset test data" (app/datafolder.py). To fill some other
folder by hand:
    LIFEOS_DATA_DIR=/some/test/folder .venv/bin/python mock_data.py
    LIFEOS_DATA_DIR=/some/test/folder .venv/bin/python main.py   (to look at it)
Only ever into a test folder: it refuses your own LifeOS_data.
"""
from datetime import date, timedelta

from app import db, templates
from app.tabs import food, gym

# name -> [(exercise, start kg or None for bodyweight, kg added per week, reps per set)]
WORKOUTS = {
    "Push": [("Bench press", 60, 1.25, [8, 8, 7]), ("Overhead press", 35, 0.5, [10, 9, 8]), ("Dips", None, 0, [12, 10, 9])],
    "Pull": [("Deadlift", 100, 2.5, [5, 5, 5]), ("Barbell row", 55, 1.25, [8, 8, 8]), ("Pull-up", None, 0, [8, 7, 6])],
    "Legs": [("Squat", 80, 2.5, [5, 5, 5, 5, 5]), ("Romanian deadlift", 70, 1.25, [10, 10, 8]), ("Leg press", 140, 5, [12, 12, 10])],
}
NOTES = {("Bench press", 3): "last rep paused", ("Squat", 5): "grind"}


def _text(name, rows):
    """The day's Gym text, written the way you'd type it."""
    lines = [name]
    for exercise, weight, reps in rows:
        at = f" @ {weight:g}" if weight is not None else ""
        lines.append(f"{exercise} {', '.join(map(str, reps))}{at}")
    return "\n".join(lines)


# name: (unit, per_amount, kcal, protein, carbs, fat)
FOODS = {
    "Oats": ("g", 100, 389, 17, 66, 7), "Milk": ("ml", 100, 64, 3.4, 4.8, 3.6),
    "Whey protein": ("scoop", 1, 120, 24, 3, 1.5), "Banana": ("banana", 1, 105, 1.3, 27, 0.4),
    "Egg": ("egg", 1, 72, 6.3, 0.4, 4.8), "Olive oil": ("ml", 100, 824, 0, 0, 91.6),
    "Sourdough bread": ("slice", 1, 140, 5, 27, 1), "Chicken breast": ("g", 100, 165, 31, 0, 3.6),
    "Basmati rice": ("g", 100, 130, 2.7, 28, 0.3), "Broccoli": ("g", 100, 34, 2.8, 7, 0.4),
    "Greek yogurt": ("g", 100, 97, 9, 3.6, 5), "Blueberries": ("g", 100, 57, 0.7, 14, 0.3),
}
# name: [(food, amount for one serving)]
RECIPES = {
    "Overnight oats": [("Oats", 80), ("Milk", 200), ("Whey protein", 1), ("Blueberries", 50)],
    "Omelette": [("Egg", 3), ("Olive oil", 5)],
    "Chicken rice bowl": [("Chicken breast", 200), ("Basmati rice", 250), ("Broccoli", 150), ("Olive oil", 7.5)],
}


def add_gym(conn, weeks=6):
    for name, exercises in WORKOUTS.items():  # blank templates, to fill in on the day
        templates.create("Gym", name, "\n".join(f"{exercise}: kg :" for exercise, *_ in exercises))
    days = 0
    start = date.today() - timedelta(weeks=weeks)
    for week in range(weeks):
        for offset, name in zip((0, 2, 4), WORKOUTS):  # Mon / Wed / Fri
            day = start + timedelta(weeks=week, days=offset - start.weekday())
            if day >= date.today():
                continue
            rows, sets = [], []
            for exercise, base, step, reps in WORKOUTS[name]:
                weight = None if base is None else base + step * week
                rows.append((exercise, weight, reps))
                sets += [{"exercise": exercise, "weight": weight, "reps": r, "note": NOTES.get((exercise, n), "")}
                         for n, r in enumerate(reps, start=1)]
            entry = gym.save_day(conn, day.isoformat(), _text(name, rows))
            if week < weeks - 1 or name != "Legs":  # leave the latest Legs day unanalysed
                gym.save_sets(conn, entry, sets)
            days += 1
    print(f"Added {days} mock workouts.")


def add_food(conn, days=14):
    foods = {}
    for name, (unit, per, kcal, p, c, f) in FOODS.items():
        food_id = food.create_food(conn, name)
        food.update_food(conn, food_id, {"unit": unit, "per_amount": per, "calories": kcal, "protein": p, "carbs": c, "fat": f})
        foods[name] = {"name": name, "unit": unit, "per_amount": per, "calories": kcal, "protein": p, "carbs": c, "fat": f}

    # Recipes are text templates: the name, then one serving's ingredients.
    line = lambda name, amount: f"- {name} {amount:g}" + ("" if name.lower().startswith(foods[name]["unit"]) else f" {foods[name]['unit']}")
    for name, ingredients in RECIPES.items():
        templates.create("Food", name, "\n".join(line(f, a) for f, a in ingredients))

    # Items as the AI would save them: each food eaten with its own numbers.
    item = lambda name, amount: {"name": name, "amount": amount, "unit": foods[name]["unit"], **food.for_amount(foods[name], amount)}
    recipe = lambda name, **changes: [item(f, changes.get(f, a)) for f, a in RECIPES[name]]
    for n in range(days, 0, -1):
        day = (date.today() - timedelta(days=n)).isoformat()
        if n % 3 == 0:
            breakfast = ("Omelette with 4 eggs, 2 slices of sourdough", recipe("Omelette", Egg=4) + [item("Sourdough bread", 2)])
        else:
            breakfast = ("Overnight oats, banana", recipe("Overnight oats") + [item("Banana", 1)])
        lunch = ("Chicken rice bowl", recipe("Chicken rice bowl"))
        if n % 4 == 0:
            dinner = ("Pizza with friends, 3 slices",
                      [{"name": "Pizza", "amount": 3, "unit": "slice", "calories": 855, "protein": 36, "carbs": 99, "fat": 33}])
        else:
            dinner = ("Chicken rice bowl, greek yogurt with blueberries",
                      recipe("Chicken rice bowl") + [item("Greek yogurt", 170), item("Blueberries", 80)])
        meals = zip(("Breakfast", "Lunch", "Dinner"), (breakfast, lunch, dinner))
        text = "\n".join(f"{meal}: {what}" for meal, (what, _) in meals)
        entry = food.save_day(conn, day, text)
        if n > 1:  # leave yesterday unanalysed, to try Edit data on
            food.save_items(conn, entry, breakfast[1] + lunch[1] + dinner[1])
    print(f"Added {len(FOODS)} foods, {len(RECIPES)} recipe templates and {days} days of meals.")


if __name__ == "__main__":
    if db.DATA_DIR.resolve() == db.YOUR_DATA_DIR.resolve():
        raise SystemExit("Mock data never goes in your LifeOS_data: set LIFEOS_DATA_DIR to a test folder.")
    conn = db.connect()
    if conn.execute("SELECT EXISTS (SELECT 1 FROM gym_log) OR EXISTS (SELECT 1 FROM foods)").fetchone()[0]:
        raise SystemExit(f"{db.DB_PATH} already has data: delete the test folder first to start over.")
    add_gym(conn)
    add_food(conn)
