-- Food: the Food Diary (free text, one entry per day), a library of foods with
-- their nutrition, and each day's items. Items are copies of the name and
-- numbers at the time (from the library or estimated by AI), not links (unlike
-- Gym's sets): what you ate each day is what counts, and the library is only a
-- shortcut for filling the numbers in. So editing or deleting a food never
-- changes past days, and renaming one doesn't rename past items.

CREATE TABLE food_log (
    id            INTEGER PRIMARY KEY,
    day           TEXT NOT NULL UNIQUE,      -- 'YYYY-MM-DD'
    body          TEXT NOT NULL DEFAULT '',
    analysed_hash TEXT,                      -- fingerprint of the text its items were saved for, to spot later edits (app use only)
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))  -- when the day was first written (app use only)
);

CREATE TABLE foods (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    unit       TEXT    NOT NULL DEFAULT 'g',   -- what amounts are counted in: g, ml, egg, scoop...
    per_amount REAL    NOT NULL DEFAULT 100,   -- the macros below are per this many units
    calories   REAL    NOT NULL DEFAULT 0,
    protein    REAL    NOT NULL DEFAULT 0,
    carbs      REAL    NOT NULL DEFAULT 0,
    fat        REAL    NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX foods_name ON foods(name COLLATE NOCASE);

-- One row per thing eaten that day, with its own numbers.
CREATE TABLE food_items (
    id       INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES food_log(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,           -- order within the day (app use only)
    name     TEXT    NOT NULL,
    amount   REAL,                       -- e.g. 150 (g), 2 (eggs); empty if not given
    unit     TEXT    NOT NULL DEFAULT '',
    calories REAL    NOT NULL DEFAULT 0, -- for the amount eaten
    protein  REAL    NOT NULL DEFAULT 0,
    carbs    REAL    NOT NULL DEFAULT 0,
    fat      REAL    NOT NULL DEFAULT 0
);
CREATE INDEX food_items_entry ON food_items(entry_id);
