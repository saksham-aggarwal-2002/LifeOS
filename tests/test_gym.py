"""Gym logic: structured sets and the exercises library."""
import pytest

from app.tabs import gym


# --- Structured sets ---


def lift(exercise, reps, weight, **extra):
    return {"exercise": exercise, "reps": reps, "weight": weight, **extra}


def workout_entry(conn, body, day="2026-10-08"):
    return gym.save_day(conn, day, body)


def test_sessions_newest_first_with_status(conn):
    old = gym.save_day(conn, "2026-10-01", "Bench 8 @ 60")
    gym.save_day(conn, "2026-10-08", "Squat")
    gym.save_sets(conn, old, [lift("Bench press", 8, 60)])
    sessions = gym.get_sessions(conn)
    assert [(s["day"], s["status"]) for s in sessions] == [("2026-10-08", "not_analysed"), ("2026-10-01", "analysed")]
    gym.save_day(conn, "2026-10-01", "Bench 8 @ 62.5")  # edited after analysis
    assert gym.get_sessions(conn)[1]["status"] == "changed"


def test_session_groups_sets_by_exercise(conn):
    e = gym.save_day(conn, "2026-10-01", "Workout")
    gym.save_sets(conn, e, [
        lift("Bench press", 8, 60), lift("Bench press", 6, 65),
        {"exercise": "Dips", "reps": 12, "weight": None},
    ])
    bench, dips = gym.get_sessions(conn)[0]["exercises"]
    assert [s["set_no"] for s in bench["sets"]] == [1, 2]
    assert [s["weight"] for s in dips["sets"]] == [None]       # bodyweight


def test_reanalysing_replaces_sets(conn):
    e = gym.save_day(conn, "2026-10-01", "Workout")
    gym.save_sets(conn, e, [lift("Bench press", 8, 60)])
    gym.save_sets(conn, e, [lift("Squat", 5, 100)])
    assert [x["exercise"] for x in gym.get_sessions(conn)[0]["exercises"]] == ["Squat"]


def test_set_needs_an_exercise(conn):
    e = gym.save_day(conn, "2026-10-01", "Workout")
    with pytest.raises(ValueError):
        gym.save_sets(conn, e, [{"exercise": " ", "reps": 5}])


def test_exercise_list_ignores_case_and_deleted_entries(conn):
    a = gym.save_day(conn, "2026-10-01", "Workout")
    b = gym.save_day(conn, "2026-10-08", "Workout")
    c = gym.save_day(conn, "2026-10-15", "Workout")
    gym.save_sets(conn, a, [lift("Bench press", 8, 60)])
    gym.save_sets(conn, b, [lift("bench press", 8, 62.5), lift("Squat", 5, 100)])
    gym.save_sets(conn, c, [lift("Bench press", 5, 70)])
    with conn:
        conn.execute("DELETE FROM gym_log WHERE id = ?", (c,))

    exercises = gym.get_exercises(conn)
    assert [(x["exercise"].lower(), x["sessions"], x["last_day"]) for x in exercises] == [
        ("squat", 1, "2026-10-08"), ("bench press", 2, "2026-10-08"),
    ]
    assert exercises[1]["top"]["weight"] == 62.5          # best set, not counting the deleted day's 70
    assert exercises[1]["exercise"] == "Bench press"   # one exercise, however it was typed


def test_deleting_entry_removes_its_sets(conn):
    e = gym.save_day(conn, "2026-10-01", "Workout")
    gym.save_sets(conn, e, [lift("Bench press", 8, 60)])
    conn.execute("DELETE FROM gym_log WHERE id = ?", (e,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0] == 0


def test_save_sets_numbers_per_exercise_and_cleans_values(conn):
    e = workout_entry(conn, "Push")
    gym.save_sets(conn, e, [
        {"exercise": "Bench press", "reps": "8", "weight": "60"},
        {"exercise": "Pull-up", "reps": 10, "weight": None},
        {"exercise": "bench press", "reps": 6, "weight": 62.5, "note": " paused "},
    ])
    rows = [dict(r) for r in conn.execute(f"SELECT {gym.SET_COLUMNS} FROM {gym.SETS} ORDER BY s.id")]
    assert [(r["exercise"], r["set_no"]) for r in rows] == [("Bench press", 1), ("Pull-up", 1), ("Bench press", 2)]
    assert rows[0]["reps"] == 8 and rows[0]["weight"] == 60
    assert rows[1]["weight"] is None  # bodyweight
    assert rows[2]["weight"] == 62.5 and rows[2]["note"] == "paused"


@pytest.mark.parametrize("bad", [
    {"exercise": "Squat", "weight": 100},                     # no reps
    {"exercise": "Squat", "reps": 5.5},                       # half a rep
    {"exercise": "Squat", "reps": -1},
    {"exercise": "Squat", "reps": "five"},
    {"exercise": "Squat", "reps": 5, "weight": -100},
])
def test_save_sets_refuses_bad_values_and_keeps_old_data(conn, bad):
    e = workout_entry(conn, "Legs")
    gym.save_sets(conn, e, [lift("Squat", 5, 100)])
    with pytest.raises(ValueError):
        gym.save_sets(conn, e, [lift("Squat", 5, 110), bad])
    assert [r[0] for r in conn.execute("SELECT weight FROM workout_sets")] == [100]


def test_saving_no_sets_clears_back_to_not_analysed(conn):
    e = workout_entry(conn, "Legs")
    gym.save_sets(conn, e, [lift("Squat", 5, 100)])
    gym.save_sets(conn, e, [])
    assert gym.get_sessions(conn)[0]["status"] == "not_analysed"
    assert gym.get_sessions(conn)[0]["exercises"] == []


# --- Exercises library ---

def names(conn):
    return [x["exercise"] for x in gym.get_exercises(conn)]


def test_saving_sets_adds_new_exercises_and_reuses_known_ones(conn):
    gym.add_exercise(conn, "Bench press")
    e = workout_entry(conn, "Push")
    gym.save_sets(conn, e, [lift("bench PRESS", 8, 60), lift("Dips", 10, None)])
    assert sorted(names(conn)) == ["Bench press", "Dips"]


def test_bad_sets_add_no_exercises(conn):
    e = workout_entry(conn, "Push")
    with pytest.raises(ValueError):
        gym.save_sets(conn, e, [lift("Bench press", 8, 60), {"exercise": "Dips"}])  # no reps
    assert names(conn) == []


def test_add_exercise_before_doing_it(conn):
    e = workout_entry(conn, "Push")
    gym.save_sets(conn, e, [lift("Bench press", 8, 60)])
    gym.add_exercise(conn, " Face pull ")
    exercises = gym.get_exercises(conn)
    assert [(x["exercise"], x["sessions"], x["last_day"]) for x in exercises] == [
        ("Bench press", 1, "2026-10-08"), ("Face pull", 0, None)]   # not done yet: last
    with pytest.raises(ValueError):
        gym.add_exercise(conn, "face PULL")                           # already there
    with pytest.raises(ValueError):
        gym.add_exercise(conn, "  ")


def test_rename_changes_every_past_set(conn):
    e = workout_entry(conn, "Push")
    gym.save_sets(conn, e, [lift("Bench", 8, 60)])
    [bench] = gym.get_exercises(conn)
    gym.rename_exercise(conn, bench["id"], "Bench press")
    assert gym.get_sessions(conn)[0]["exercises"][0]["exercise"] == "Bench press"
    gym.rename_exercise(conn, bench["id"], "bench press")             # just capitals: fine


def test_rename_to_another_exercises_name_is_refused(conn):
    a, b = gym.add_exercise(conn, "Bench"), gym.add_exercise(conn, "Bench press")
    with pytest.raises(ValueError, match="already"):
        gym.rename_exercise(conn, a, "BENCH PRESS")


def test_delete_only_when_unused(conn):
    unused = gym.add_exercise(conn, "Face pull")
    e = workout_entry(conn, "Push")
    gym.save_sets(conn, e, [lift("Bench press", 8, 60)])
    used = [x["id"] for x in gym.get_exercises(conn) if x["exercise"] == "Bench press"][0]
    with pytest.raises(ValueError, match="sets logged"):
        gym.delete_exercise(conn, used)
    gym.delete_exercise(conn, unused)
    assert names(conn) == ["Bench press"]
