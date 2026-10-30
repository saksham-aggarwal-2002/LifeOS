-- To Do: lists and the tasks inside them.

CREATE TABLE lists (
    id       INTEGER PRIMARY KEY,
    name     TEXT    NOT NULL,
    position INTEGER NOT NULL DEFAULT 0   -- order in the sidebar
);

CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY,
    list_id      INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    title        TEXT    NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,   -- 0 = open, 1 = done
    completed_at TEXT,                          -- when it was ticked off
    do_date      TEXT,                          -- 'YYYY-MM-DD' or NULL
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),  -- when it was added (UTC); orders open tasks
    deleted_at   TEXT                           -- set = in Recently deleted
);

CREATE INDEX tasks_list       ON tasks(list_id);
CREATE INDEX tasks_do_date    ON tasks(do_date);
CREATE INDEX tasks_deleted_at ON tasks(deleted_at);

-- Every install starts with one list.
INSERT INTO lists (name, position) VALUES ('Tasks', 0);
