-- Body: one weigh-in per day, in kg.
CREATE TABLE weights (
    day TEXT PRIMARY KEY,   -- 'YYYY-MM-DD'
    kg  REAL NOT NULL CHECK (kg > 0)   -- above 0
);
