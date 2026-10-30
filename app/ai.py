"""The only place that talks to an AI provider (OpenAI for now).

The AI's job is understanding text; it returns structured data in a fixed
schema (checked by the SDK), and Python does everything else: checking ids,
unit maths, macros, saving. Swapping provider means changing only this file.

Settings come from the project's .env file (or the environment):
    OPENAI_API_KEY   required
    OPENAI_MODEL     optional, defaults to DEFAULT_MODEL

The instructions sent with each request live in the data folder, so they can
be read and edited like everything else you keep:
    AI Prompts/Gym.txt    turning a Gym Diary day into sets
    AI Prompts/Food.txt   turning a Food Diary day into foods eaten
They're read fresh for every request. The versions below are the defaults,
written there when a file is missing. The shape of what comes back (the
schemas below) is fixed by the code: a prompt can't add or rename fields.
"""
import json
import os
from typing import Optional

from pydantic import BaseModel

from app import db
from app.db import PROJECT_DIR

DEFAULT_MODEL = "gpt-5.4-mini"


def _settings():
    """KEY=value lines from .env, with real environment variables winning."""
    values = {}
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                values[key.strip()] = value.strip().strip("\"'")
    return {**values, **{k: v for k, v in os.environ.items() if k.startswith("OPENAI_")}}


def _ask(instructions, data, schema):
    """One request: instructions + JSON input in, an instance of `schema` out."""
    settings = _settings()
    if not settings.get("OPENAI_API_KEY"):
        raise ValueError("No OpenAI key: add OPENAI_API_KEY to the .env file")
    import openai  # imported here so the app starts without it

    client = openai.OpenAI(api_key=settings["OPENAI_API_KEY"], timeout=60)
    try:
        response = client.responses.parse(
            model=settings.get("OPENAI_MODEL") or DEFAULT_MODEL,
            instructions=instructions,
            input=json.dumps(data, ensure_ascii=False),
            text_format=schema,
            reasoning={"effort": "medium"},  # time to think: far fewer misread sets (slower, ~10 s)
            store=False,
        )
    # Short messages for the app's toast instead of raw API errors.
    except openai.AuthenticationError as err:
        raise ValueError(f"OpenAI rejected the key in .env: {_message(err)}") from None
    except openai.RateLimitError as err:
        raise ValueError(f"OpenAI limit reached: {_message(err)}") from None
    except openai.APIConnectionError:
        raise ValueError("Couldn't reach OpenAI (check the internet connection)") from None
    except openai.APIStatusError as err:
        raise ValueError(f"OpenAI error: {_message(err)}") from None
    if response.output_parsed is None:
        raise ValueError("The AI didn't return usable data")
    return response.output_parsed


def _message(err):
    """The human-readable part of an OpenAI API error."""
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        return (body.get("error") or body).get("message") or str(err)
    return str(err)


# --- Workouts ---

class WorkoutSet(BaseModel):
    exercise: str
    weight: Optional[float]        # kg; None = bodyweight
    reps: int
    note: str


class Workout(BaseModel):
    sets: list[WorkoutSet]


WORKOUT_INSTRUCTIONS = """\
You turn a gym log, written free-form by one person, into individual sets.
Input JSON: {"text": the log, "known_exercises": names they've used before}.

Rules:
- One output item per set actually done, in the order written.
  "SETSxREPS @ WEIGHT": "3x8 @ 60" is three sets of 8 reps at 60, so three
  separate items (60, 8), (60, 8), (60, 8), never one item.
  "8, 8, 7 @ 60" is three sets.
  "WEIGHTxREPS" in a list without "@": "60x8, 62.5x6" is two sets with
  different weights.
- Their usual format is "Exercise: WEIGHT: REPS, REPS, ...":
  "Bench press: 10kg : 5,5,5" is three sets of 5 reps at 10kg.
  When several weights are listed, they pair up with the reps in order:
  "Curl : 5,5, 10 kg : 8,8,8" is 8 reps at 5kg, 8 reps at 5kg, 8 reps at 10kg.
  No weight ("Pull ups: 6,8,9") means bodyweight.
- Use a known exercise name (exact spelling) when it's the same exercise,
  e.g. "bench" -> "Bench press". Otherwise use the exercise's full common
  name, capitalised, with abbreviations spelled out: "OHP" -> "Overhead
  press", "RDL" -> "Romanian deadlift".
- weight: the kg lifted; null for bodyweight exercises (pull-ups, dips,
  push-ups) unless extra weight is given. Weights are kg unless lb/lbs is
  written: then convert to kg (× 0.4536, rounded to 0.1).
- Skip lines with nothing done: headings like "Push 1", blank template lines
  like "Bench press: kg :", and anything that isn't a lift with reps.
- note: anything else said about that set (e.g. "paused", "failed last rep"),
  otherwise "". Never invent numbers.
"""


def parse_workout(text, known_exercises):
    """The sets in a Gym box's text, as dicts for gym.save_sets."""
    result = _ask(prompt("Gym"), {"text": text, "known_exercises": known_exercises}, Workout)
    return [s.model_dump() for s in result.sets]


# --- Food ---

class FoodItem(BaseModel):
    name: str
    food_id: Optional[int]          # a saved food's id, or null
    amount: Optional[float]         # saved food: in its unit; otherwise as written, if given
    unit: str
    calories: Optional[float]       # not a saved food: estimates for the whole item
    protein: Optional[float]
    carbs: Optional[float]
    fat: Optional[float]


class Meal(BaseModel):
    items: list[FoodItem]


FOOD_INSTRUCTIONS = """\
You turn a food diary, written free-form by one person, into the foods eaten,
using their saved foods wherever they match.
Input JSON: {"text": the diary, "foods": [{id, name, unit, per_amount}]}.

Each thing eaten becomes one item:
- A saved food: food_id = its id; amount = how much, converted to that food's
  unit ("2 eggs" with unit "egg" is 2; "150g" with unit "g" is 150; "2 pieces
  of bread" with unit "slice" is 2); unit = the food's unit; name = its name.
  calories/protein/carbs/fat = null (they're worked out from the library).
- Anything else: food_id = null; name = a short name as written, e.g. "Pizza";
  amount and unit as written if given ("3 slices": 3, "slice"), else null and
  ""; give your best estimate of calories, protein, carbs and fat (grams) for
  the whole amount eaten.
A recipe is often written as its name followed by its ingredients ("- Oats 80
g"): then each ingredient line is an item and the name line isn't. A dish
named without ingredients is one item. Skip meal labels ("Breakfast:") and
anything not eaten. Never use a food_id that isn't in the input.
"""


def parse_food(text, foods):
    """The items in a Food box's text, as FoodItem dicts (see AI Prompts/Food.txt)."""
    result = _ask(prompt("Food"), {"text": text, "foods": foods}, Meal)
    return [i.model_dump() for i in result.items]


# --- Prompts: text files in the data folder ---

DEFAULT_PROMPTS = {"Gym": WORKOUT_INSTRUCTIONS, "Food": FOOD_INSTRUCTIONS}


def prompts_folder():
    """LifeOS_data/AI Prompts (follows db.DATA_DIR, so tests use a temp folder)."""
    return db.DATA_DIR / "AI Prompts"


def write_missing_prompts():
    """Put the default prompt in the data folder for any that isn't there yet."""
    prompts_folder().mkdir(parents=True, exist_ok=True)
    for name, text in DEFAULT_PROMPTS.items():
        path = prompts_folder() / f"{name}.txt"
        if not path.exists():
            path.write_text(text, encoding="utf-8")


def prompt(name):
    """The instructions for one kind of request, as saved in the data folder."""
    write_missing_prompts()
    text = (prompts_folder() / f"{name}.txt").read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"AI Prompts/{name}.txt is empty: write the instructions there, or delete it to get the default back")
    return text
