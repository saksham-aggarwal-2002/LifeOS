"""LifeOS_data/README.md: a description of everything in the data folder, written by
the app on every launch, so it always matches what's actually stored.

The data folder is the permanent part of LifeOS; the app is just a way to view
and edit it. This file explains it to anyone (or anything) opening the folder:
what each file holds, and every table with its columns, grouped by the tab
that owns it. Tables come from the database itself; the explanations come from
the comments in schema/*.sql.
"""
import re

from app import db

FILE_NAME = "README.md"

# Data kept as plain text files, not in the database, per owning tab.
TEXT_FILES = {
    "Gym": ["`Templates/Gym/<name>.txt`: workout templates. The file name is the template's name; "
            "the + on a day's box copies its text into that day.",
            "`AI Prompts/Gym.txt`: the instructions sent to the AI when it turns a day's text into sets. "
            "Edit it to change how the text is read; delete it to get the default back."],
    "Food": ["`Templates/Food/<name>.txt`: food templates (e.g. recipes), the same way.",
             "`AI Prompts/Food.txt`: the instructions sent to the AI when it turns a day's text into foods eaten, "
             "the same way."],
    "Journal": ["`Journal Entries/YYYY-MM-DD.txt`: one file per day. The first line is the date, "
                "written by the app; the rest is the day's text."],
}


def _comment_block(lines):
    """The text of a run of `-- ` comment lines."""
    return " ".join(line.strip()[2:].strip() for line in lines)


def _parse_schema(sql):
    """(tab name, tab description, {table: description}) from one schema file."""
    lines = sql.splitlines()
    header = []
    for line in lines:
        if not line.strip().startswith("--"):
            break
        header.append(line)
    text = _comment_block(header)
    tab, _, about = text.partition(":")
    # A table's description: the comment lines just above it (not the header).
    tables, above = {}, []
    for line in lines[len(header):]:
        stripped = line.strip()
        match = re.match(r"CREATE TABLE (\w+)", stripped)
        if match:
            tables[match.group(1)] = _comment_block(above)
        above = above + [line] if stripped.startswith("--") else []
    about = about.strip()
    return tab.strip(), about[:1].upper() + about[1:], tables


def _column_comments(schema_sql, table):
    """{column: its trailing -- comment} from the table's CREATE TABLE in its
    schema file (the file, not the database, so comments can be reworded)."""
    match = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", schema_sql, re.S)
    comments = {}
    for line in (match.group(1) if match else "").splitlines():
        match = re.match(r"\s*(\w+)\s+\w+.*?--\s*(.+)$", line)
        if match:
            comments[match.group(1)] = match.group(2).strip()
    return comments


def _unique_columns(conn, table):
    """{column: 'unique' or 'unique, ignoring capitals'} for single-column unique indexes."""
    unique = {}
    for index in conn.execute(f"PRAGMA index_list({table})"):
        if not index["unique"] or index["origin"] == "pk":
            continue
        columns = [c["name"] for c in conn.execute(f"PRAGMA index_info({index['name']})")]
        if len(columns) == 1:
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (index["name"],)).fetchone()[0] or ""
            unique[columns[0]] = "unique, ignoring capitals" if "NOCASE" in sql.upper() else "unique"
    return unique


def _table(conn, table, about, schema_sql):
    comments = _column_comments(schema_sql, table)
    unique = _unique_columns(conn, table)
    links = {fk["from"]: fk for fk in conn.execute(f"PRAGMA foreign_key_list({table})")}
    rows = []
    for col in conn.execute(f"PRAGMA table_info({table})"):
        name = col["name"]
        notes = []
        if col["pk"]:
            notes.append("primary key")
        elif col["notnull"]:
            notes.append("required")
        if name in unique:
            notes.append(unique[name])
        if name in links:
            fk = links[name]
            on_delete = {"CASCADE": "deleted with it", "RESTRICT": "blocks deleting it"}.get(fk["on_delete"], "")
            notes.append(f"→ {fk['table']}.{fk['to']}" + (f" ({on_delete})" if on_delete else ""))
        if col["dflt_value"] is not None:
            notes.append(f"default {col['dflt_value']}")
        if name in comments:
            notes.append(comments[name])
        rows.append(f"| {name} | {col['type']} | {'; '.join(notes).replace('|', chr(92) + '|')} |")
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return [
        f"#### `{table}` ({count} row{'' if count == 1 else 's'})", "",
        *([about, ""] if about else []),
        "| column | type | notes |", "|---|---|---|", *rows, "",
    ]


def render(conn):
    """The README's text for the database `conn` and the files beside it."""
    out = [
        "# LifeOS data", "",
        "Everything LifeOS keeps lives in this folder. The app is only a way to view and edit it:",
        "delete the app and this folder still holds all your data, in formats you can open without it.", "",
        "This file is rewritten by the app every time it starts, from the database itself,",
        "so it always matches what's stored. Edits made to it by hand will be replaced.", "",
        "## What's here", "",
        "- `lifeos.db`: an SQLite database with every table below (open it with any SQLite tool).",
        "- `Journal Entries/`, `Templates/`, `AI Prompts/`: data kept as plain text files.",
        "- `backups/`: a copy of the database and the text-file folders from each day the app was opened (the newest 14).",
        "- `README.md`: this file.", "",
        "## Data by tab", "",
        "Each tab of the app owns its own data. The Overview tab owns nothing: it shows and edits",
        "the day's data from the other tabs. Settings owns nothing either.", "",
    ]
    tabs = []
    for path in db.schema_files():
        sql = path.read_text()
        tab, about, tables = _parse_schema(sql)
        tabs.append((tab, about, tables, sql))
    for tab in TEXT_FILES:
        if tab not in [t[0] for t in tabs]:
            tabs.append((tab, "", {}, ""))
    for tab, about, tables, sql in tabs:
        out += [f"### {tab}", ""]
        if about:
            out += [about, ""]
        for table, table_about in tables.items():
            out += _table(conn, table, table_about, sql)
        if tab in TEXT_FILES:
            out += ["Text files:", "", *[f"- {line}" for line in TEXT_FILES[tab]], ""]
    return "\n".join(out)


def write(conn):
    """Write LifeOS_data/README.md (follows db.DATA_DIR, so tests use a temp folder)."""
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (db.DATA_DIR / FILE_NAME).write_text(render(conn), encoding="utf-8")
