-- Gym: the Gym Diary (free text, one entry per day), the sets extracted from
-- it (by hand or by AI), and an exercises library the sets point at.
-- Sets are linked to their exercise, not copies of its name (unlike Food's
-- items): an exercise is what you track over time, so every set of it must
-- stay together. Renaming an exercise renames it in every past set, and one
-- with sets logged can't be deleted.

CREATE TABLE gym_log (
    id            INTEGER PRIMARY KEY,
    day           TEXT NOT NULL UNIQUE,      -- 'YYYY-MM-DD'
    body          TEXT NOT NULL DEFAULT '',
    analysed_hash TEXT,                      -- fingerprint of the text its sets were saved for, to spot later edits (app use only)
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))  -- when the day was first written (app use only)
);

-- Every exercise, done or not yet. Renaming one renames it in every past set;
-- one with sets logged can't be deleted.
CREATE TABLE exercises (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE UNIQUE INDEX exercises_name ON exercises(name COLLATE NOCASE);

-- One row per set. Deleting a day deletes its sets.
CREATE TABLE workout_sets (
    id          INTEGER PRIMARY KEY,
    entry_id    INTEGER NOT NULL REFERENCES gym_log(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    set_no      INTEGER NOT NULL,   -- 1, 2, 3... per exercise within the day
    reps        INTEGER,
    weight      REAL,               -- kg; empty = bodyweight
    note        TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX workout_sets_entry    ON workout_sets(entry_id);
CREATE INDEX workout_sets_exercise ON workout_sets(exercise_id);

