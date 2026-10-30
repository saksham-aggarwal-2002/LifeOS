"""Extract Structured Data, with a fake AI: Python checks ids and does the maths."""
import pytest

from app import ai, extract
from app.tabs import food, gym

DAY = "2026-10-26"


def fake(result):
    """A stand-in for an ai.parse_* function that records what it was given."""
    def parse(*args):
        parse.called_with = args
        return result
    return parse


def test_workout_sets_saved_and_known_names_passed(conn):
    old = gym.save_day(conn, "2026-10-01", "Bench 8 @ 60")
    gym.save_sets(conn, old, [{"exercise": "Bench press", "reps": 8, "weight": 60}])
    e = gym.save_day(conn, DAY, "Push\nbench 8, 7 @ 62.5\ndips 10")
    parse = fake([
        {"exercise": "Bench press", "weight": 62.5, "reps": 8, "note": ""},
        {"exercise": "Bench press", "weight": 62.5, "reps": 7, "note": "grind"},
        {"exercise": "Dips", "weight": None, "reps": 10, "note": ""},
    ])
    assert extract.extract_workout(conn, e, parse) == {"count": 3}
    assert parse.called_with == ("Push\nbench 8, 7 @ 62.5\ndips 10", ["Bench press"])
    session = gym.get_sessions(conn)[0]
    assert session["status"] == "analysed"
    assert [(x["exercise"], len(x["sets"])) for x in session["exercises"]] == [("Bench press", 2), ("Dips", 1)]


def test_nothing_to_extract_still_counts_as_done(conn):
    e = gym.save_day(conn, DAY, "Push 1\nBench press: kg :")
    extract.extract_workout(conn, e, fake([]))
    assert gym.get_sessions(conn)[0]["status"] == "analysed"


def test_bad_ai_output_keeps_old_data(conn):
    e = gym.save_day(conn, DAY, "Squat 5 @ 100")
    gym.save_sets(conn, e, [{"exercise": "Squat", "reps": 5, "weight": 100}])
    gym.save_day(conn, DAY, "Squat 5 @ 110")
    with pytest.raises(ValueError):
        extract.extract_workout(conn, e, fake([{"exercise": "", "weight": 110, "reps": 5, "note": ""}]))
    assert gym.get_sessions(conn)[0]["exercises"][0]["sets"][0]["weight"] == 100


@pytest.fixture
def library(conn):
    egg = food.create_food(conn, "Egg")
    food.update_food(conn, egg, {"unit": "egg", "per_amount": 1, "calories": 70, "protein": 6})
    oil = food.create_food(conn, "Oil")
    food.update_food(conn, oil, {"unit": "ml", "per_amount": 100, "calories": 800, "fat": 90})
    return {"egg": egg, "oil": oil}


def item(name, food_id=None, amount=None, unit="", **macros):
    return {"name": name, "food_id": food_id, "amount": amount, "unit": unit, **{m: macros.get(m) for m in food.MACROS}}


def test_saved_foods_get_library_numbers_others_keep_estimates(conn, library):
    e = food.save_day(conn, DAY, "Omelette\n- Egg 3\n- Oil 15 ml\nand a flat white")
    parse = fake([
        item("egg", library["egg"], 3),
        item("Oil", library["oil"], 15),
        item("Flat white", calories=120, protein=7, carbs=10, fat=6),
    ])
    assert extract.extract_food(conn, e, parse) == {"count": 3}
    text, foods = parse.called_with
    assert {"id": library["egg"], "name": "Egg", "unit": "egg", "per_amount": 1} in foods
    [entry] = food.get_diary(conn)
    assert [(i["name"], i["amount"], i["unit"], i["calories"], i["fat"]) for i in entry["items"]] == [
        ("Egg", 3, "egg", 210, 0), ("Oil", 15, "ml", 120, 13.5), ("Flat white", None, "", 120, 6)]
    assert entry["status"] == "analysed"


def test_unknown_food_id_needs_an_estimate(conn, library):
    e = food.save_day(conn, DAY, "mystery stew")
    extract.extract_food(conn, e, fake([item("Stew", 999, 1, "bowl", calories=400, protein=20, carbs=30, fat=15)]))
    assert food.get_diary(conn)[0]["items"][0]["calories"] == 400
    with pytest.raises(ValueError):
        extract.extract_food(conn, e, fake([item("Stew", 999, 1)]))


def test_missing_entry_refused(conn):
    with pytest.raises(ValueError):
        extract.extract_workout(conn, 999, fake([]))


def test_schemas_are_valid_for_structured_output():
    from openai.lib._pydantic import to_strict_json_schema
    for schema in (ai.Workout, ai.Meal):
        assert to_strict_json_schema(schema)["additionalProperties"] is False


def test_settings_read_from_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('# comment\nOPENAI_API_KEY="abc"\nOPENAI_MODEL=some-model\n')
    monkeypatch.setattr(ai, "PROJECT_DIR", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert ai._settings() == {"OPENAI_API_KEY": "abc", "OPENAI_MODEL": "some-model"}


def test_prompts_live_in_the_data_folder(data_dir):
    assert ai.prompt("Gym") == ai.WORKOUT_INSTRUCTIONS            # missing: the default is written
    path = data_dir / "AI Prompts" / "Food.txt"
    assert path.read_text() == ai.FOOD_INSTRUCTIONS
    path.write_text("My own food instructions")
    assert ai.prompt("Food") == "My own food instructions"         # edits are what gets sent
    path.write_text("  ")
    with pytest.raises(ValueError):
        ai.prompt("Food")
    path.unlink()
    assert ai.prompt("Food") == ai.FOOD_INSTRUCTIONS              # deleted: back to the default
