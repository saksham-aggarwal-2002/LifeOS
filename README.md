# LifeOS

A personal Mac desktop app for running my life: tasks, gym, food, journal and
body measurements, one tab each. Only one person uses it, on one Mac.

It's a pywebview window showing plain HTML/CSS/JS. The JS calls Python
functions directly, and Python stores everything in an SQLite database plus a
few folders of plain text files. There is no web server, framework or build
step.

This README is the map of the project, written for me and for any AI agent
working on it: how it's set up, the ideas behind it, the workflow for
changing it, and the steps for adding to it. **Read it before changing
anything.**

---

## Contents

1. [Philosophy](#philosophy)
2. [Running it](#running-it)
3. [Your data vs test data: the workflow for changing the app](#your-data-vs-test-data-the-workflow-for-changing-the-app)
4. [How the code is laid out](#how-the-code-is-laid-out)
5. [How a click becomes saved data](#how-a-click-becomes-saved-data)
6. [The data folder](#the-data-folder)
7. [The tabs](#the-tabs)
8. [Shared pieces](#shared-pieces)
9. [Adding a new tab](#adding-a-new-tab)
10. [Adding a feature or changing tables](#adding-a-feature-or-changing-tables)
11. [Code conventions](#code-conventions)
12. [Rules for AI agents](#rules-for-ai-agents)
13. [Ideas not built yet](#ideas-not-built-yet)

---

## Philosophy

These are the decisions everything else follows from. When something new
doesn't obviously fit, decide it the way these would.

- **The data folder is what's permanent; the app is just a way to view and
  edit it.** Everything I keep lives in one folder, `LifeOS_data`, beside
  the code (not inside it). It's kept in formats that open without the app:
  an SQLite database, plain `.txt` files, and a generated `README.md` that
  explains every table and file. If the app were deleted, nothing would be
  lost.
- **Fewest layers possible.** The stack is pywebview, the standard library's
  `sqlite3`, and vanilla JS. There's no Flask, ORM, React, bundler or
  templating. Add a dependency only when it removes real work (the `openai`
  SDK is the only one so far). The code is small enough to read end to end.
- **Each tab owns its data.** A tab has its own tables, its own Python
  module and its own JS file. Other tabs reach its data only through its
  functions. The Overview owns nothing: it shows each tab's piece of one day
  and saves back through that tab.
- **Write freely first; structure comes after.** Gym and Food are typed as
  free text, one box per day, like a notebook. Structured rows (sets, foods
  eaten) are extracted from that text by AI, or typed in by hand, and can
  always be edited. The text is the source; the rows are what gets counted.
- **The AI only understands text.** It turns text into a fixed shape (a
  pydantic schema). Python does everything else: checking ids, doing the
  maths, saving. `app/ai.py` is the only file that talks to an AI provider.
  The prompts are text files in the data folder, so they can be edited like
  any other data.
- **Plain text where text is the point.** Journal entries, templates and AI
  prompts are `.txt` files, not database rows.
- **The app gives a complete picture of the data in its folder.** The tabs
  show the actual data I care about: what I logged, ate, lifted, weighed.
  Columns that only help the app work don't need to be in the tabs; these
  are things like `analysed_hash`, `position` and `created_at`. They must
  still be documented in the data folder's `README.md`, which Settings
  shows. So the structure (schema) of every table is always visible, and
  nothing is stored that I can't find out about.
- **Full transparency about how data is stored.** Always explain and keep
  track of how the database is structured, for me as the user. The app is
  only a way to keep track of life data, so I want to see:
  - the schema;
  - the processes that change data (e.g. what the AI does to a day's text);
  - exactly where and how each piece of data is stored.

  This is why the data folder has a generated `README.md`, why Settings
  shows it, and why the schema files carry explanations.
- **Simple over clever, and no keeping fake data alive.** While a feature
  is being built, its data is mock data. Change the tables by editing
  `schema/` in place and rebuild the test data; don't write upgrade code to
  keep mock rows. My own data is different: see
  [the workflow](#your-data-vs-test-data-the-workflow-for-changing-the-app).
- **Built step by step, so I learn it.** Changes are made one step at a
  time, each leaving the app working, with an explanation of what was
  added and why. Prefer a few clear changes to a big rewrite.

---

## Running it

### Set up and run

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

### Install as an app

```sh
./build_app.sh
```

This puts `LifeOS.app` in `/Applications` (Dock, Spotlight, Launchpad). It's a
py2app *alias* build: the app runs `main.py` from this folder with `.venv`'s
Python. So:

- After editing code, quit and reopen the app; no rebuild is needed.
- Rerun the script only after changing `setup.py` or the icon. To change the
  icon, edit `assets/make_icon.py`, then delete `assets/LifeOS.icns`.
- This folder and `.venv` must stay where they are.

### AI (Extract Structured Data)

Put the OpenAI key in a `.env` file in this folder. It's gitignored, so it's
never committed.

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini   # optional; the default is in app/ai.py
```

Without a key, the app works normally; only the "Extract" buttons report
that the key is missing.

### Tests

```sh
.venv/bin/python -m pytest -q
```

Every test gets its own temporary database and data folder
(`tests/conftest.py` sets `LIFEOS_DATA_DIR` to a temp folder before the app is
imported), so tests never touch `LifeOS_data` or `test_data`.

The tests that call the real AI are skipped unless you ask for them, because
they cost a few API calls:

```sh
LIFEOS_LIVE_AI=1 .venv/bin/python -m pytest tests/test_extract_live.py
```

---

## Your data vs test data: the workflow for changing the app

The app can point at two data folders. You choose between them in
**Settings → Data folder**:

| Choice | Folder | Holds |
|---|---|---|
| **Your data** (the default) | `../LifeOS_data` (beside this folder) | My real data. Never in git. |
| **Test data** | `./test_data` (inside this folder, gitignored) | Mock data (`mock_data.py`), for trying changes on. |

The choice is saved in `data_folder.txt` (gitignored). It's shared by the
installed app and `python main.py`. While the app isn't on my own data, an
orange **Test data** badge shows in the tab bar. `app/datafolder.py` does the
switching.

### The workflow

1. **Normal use:** the app is on *Your data*.
2. **Changing the app:** switch to *Test data*.
   - Build the change, and update `mock_data.py` so the test data shows it.
   - A new test folder fills itself with mock data. **Reset test data** in
     Settings starts it again.
   - If the tables changed so that the test database no longer matches
     `schema/`, the test folder is rebuilt automatically when it's opened.
3. **Changing tables when my own data exists:** write a one-off
   **conversion script**. It reads my `LifeOS_data` database and rewrites it
   in the new shape. Then switch back to *Your data*.

Until step 3 is done, my own folder doesn't match the new tables, so the app
refuses it (`db.check_schema`) rather than guess. At launch it then opens the
test folder instead, and Settings says why. My own folder is never changed
automatically.

### Conversion scripts (step 3)

None exist yet; this is how to write one when it's needed:

- **Where:** `conversions/YYYY-MM-DD-what-changed.py`.
- **What it reads and writes:**
  1. Read the old database.
  2. Create a new database from the current `schema/` (`db.create`).
  3. Copy every row across, transformed as needed.
  4. Check the row counts match.
  5. Replace the old file only at the end.
- **Safety:** first make a dated copy of the old database beside it (the app
  also keeps daily backups in `LifeOS_data/backups/`). Run it on a copy of
  my data first, then for real **only when I say so**.

---

## How the code is laid out

```
LifeOS/
├── main.py            Starts the app: datafolder.start() picks and opens the data folder,
│                      then opens the window with Api(conn).
├── app/
│   ├── api.py         The JS↔Python bridge: every public method is callable from JS.
│   │                  Thin wrappers, grouped by tab, named <tab>_<action>.
│   ├── db.py          Where the data folder is (use()), connect() + creating tables from schema/,
│   │                  check_schema() (refuses an out-of-date database), daily backups.
│   ├── datafolder.py  Your data vs test data: start(), switch(), reset_test(), status().
│   ├── datadoc.py     Writes LifeOS_data/README.md from the live database + schema/ comments.
│   ├── daylog.py      The "one text entry per day" table logic Gym and Food share.
│   ├── templates.py   Templates as text files: Templates/<Gym|Food>/<name>.txt.
│   ├── ai.py          The only code that talks to OpenAI: prompts, response schemas, errors.
│   ├── extract.py     Text -> structured rows: calls ai.py, checks the result, saves it through
│   │                  the tab's own save function (the same one hand edits use).
│   └── tabs/          One module per tab: plain functions taking `conn`, returning plain data.
│       ├── log.py       Overview (named "log" in code): reads each tab's day, stores nothing.
│       ├── todo.py      Lists, tasks, My Day, calendar, Recently deleted.
│       ├── gym.py       Gym Diary, sets, exercises library.
│       ├── food.py      Food Diary, foods library, each day's items.
│       ├── journal.py   One .txt file per day.
│       ├── body.py      Weight per day.
│       └── settings.py  The data folder's README for the Settings page.
├── schema/            One .sql file per tab: that tab's tables as they are now.
│                      Comments in them become the data folder's README.
├── ui/
│   ├── index.html     Every tab's layout: one <section id="tab-<name>"> each, plus the tab bar.
│   ├── style.css      All styles; light/dark via CSS variables at the top.
│   ├── app.js         Shared helpers: call(), el(), dates, formatting, popovers, menus,
│   │                  date picker, toasts, delete buttons, tab switching, Extract buttons.
│   ├── daylog.js      Shared day pieces: dayBar, dayBox, weightBox, diaryDay, autosave.
│   ├── templates.js   The shared Templates view (Gym and Food).
│   └── tabs/          One script per tab, matching app/tabs/.
├── tests/             pytest, one file per module.
├── mock_data.py       Fake gym, food and template data for the test folder.
├── assets/            The app icon and the script that draws it.
├── setup.py, build_app.sh   Build /Applications/LifeOS.app (py2app alias mode).
└── requirements.txt   Exact versions of everything installed in .venv.
```

These are not committed (`.gitignore`): `.venv/`, `build/`, `dist/`, `.env`,
`test_data/`, `data_folder.txt`, and caches.

---

## How a click becomes saved data

Take ticking a task:

1. **JS** (`ui/tabs/todo.js`) calls `await call("todo_toggle_task", id)`.
   `call()` in `ui/app.js` waits for pywebview, then runs
   `window.pywebview.api.todo_toggle_task(id)`.
2. **Bridge** (`app/api.py`): `Api.todo_toggle_task` passes its connection to
   `todo.toggle_task(self._conn, id)`.
3. **Logic** (`app/tabs/todo.py`): plain SQL inside `with conn:`, which commits
   on success and rolls back on error.
4. **Back in JS:** the return value arrives as JSON. A Python `ValueError`
   arrives as a rejected promise; the UI shows its message as a toast. So
   Python is where values are checked, and its messages are written for me
   to read.

Other things to know:

- **Scripts:** the JS files are classic scripts that share one global scope,
  loaded in order by `index.html`: `app.js`, then `daylog.js` and
  `templates.js`, then the tabs.
- **Building the page:** each tab draws its part of the page with `el()` from
  data it fetched. There's no templating and no `innerHTML` with data in it,
  so text is never run as HTML.
- **Switching tabs:** this fires a `tabshown` event. Each tab reloads itself
  when shown, because other tabs may have changed its data.
- **Autosave:** typing saves after a short pause (`debounce`). Changing day,
  tab or folder saves anything still pending first (`dayFlush`,
  `templatesFlush`).

---

## The data folder

`LifeOS_data/` (and `test_data/`, which has the same layout):

```
lifeos.db            SQLite: every tab's tables (schema/*.sql)
Journal Entries/     YYYY-MM-DD.txt, one per day
Templates/Gym/       <name>.txt: workout templates
Templates/Food/      <name>.txt: food templates (recipes etc.)
AI Prompts/          Gym.txt, Food.txt: the instructions sent to the AI
backups/             a copy of the database and text folders per day opened (newest 14)
README.md            generated: every file and table explained
```

### Tables

- **Defined in `schema/<tab>.sql`**, with the files listed in order in
  `db.SCHEMA_FILES`. A new database gets all of them at once.
- **There are no migrations.** On every launch `db.check_schema` compares the
  database's tables, columns, links and unique indexes with a fresh build
  from `schema/`, and refuses one that differs. Comment-only edits are fine.

### The generated README

`LifeOS_data/README.md` is rewritten on every launch, and when Settings opens,
by `app/datadoc.py`. Its explanations come from the comments in `schema/`:

- the header comment of a file describes the tab;
- the comment just above a `CREATE TABLE` describes the table;
- the trailing `-- comment` on a column line describes the column.

Text-file data is described in `datadoc.TEXT_FILES`. **So write good
comments in schema files, and never edit the generated README by hand.**
Settings shows this README.

### Other data rules

- **Backups:** `db.backup` runs at every launch. It makes one copy per day of
  the database and the text folders, and keeps the newest 14.
- **AI prompts:** read fresh for every request. The defaults in `app/ai.py`
  are only written when a file is missing. To pick up new default wording,
  delete the file.
- **Dates:** always `'YYYY-MM-DD'` strings in local time, in both Python and
  JS.

---

## The tabs

| Tab | Owns | Notes |
|---|---|---|
| **Overview** (`log`) | nothing | One day from every tab: today's tasks (tick them off), the Food, Gym and Journal boxes, and weight. Saves through each tab. |
| **To Do** | `lists`, `tasks` | Lists (reorder by dragging), My Day (do date ≤ today), week calendar with drag to schedule, Recently deleted (kept 30 days). |
| **Gym** | `gym_log`, `workout_sets`, `exercises`, `Templates/Gym/`, `AI Prompts/Gym.txt` | **Gym Diary:** the day's box, then every day's text beside its sets. **Exercises:** the library, renamed in place. **Templates.** Weight is kg; empty means bodyweight. |
| **Food** | `food_log`, `food_items`, `foods`, `Templates/Food/`, `AI Prompts/Food.txt` | **Food Diary:** the day's box, then every day's text beside its items. **Foods:** the library, macros per an amount of a unit. **Templates.** |
| **Journal** | `Journal Entries/*.txt` | The day's box, then every entry. |
| **Body** | `weights` | **Weight:** the day's box, then a table of every weigh-in. More measurements will go here. |
| **Settings** | nothing | Data folder choice; the data folder's README. |

Gym and Food each have an **Extract** button. It sends every day whose text
has no structured data yet, or whose text has changed since, to the AI one
at a time. A day's "changed" status comes from a hash of the text saved with
its rows (`analysed_hash`).

---

## Shared pieces

Reuse these rather than writing new versions.

**Python**

- **`app/daylog.py`:** a tab's one-entry-per-day text table, its structured
  rows, and its analysis status. Gym and Food use it. A new "free text per
  day, with rows extracted" tab adds its table to `daylog.TABLES`.
- **`app/templates.py`:** templates as text files. `TABS` lists which tabs
  have them.
- **`app/extract.py` with `app/ai.py`:** the pattern for AI extraction. A
  pydantic schema and default prompt go in `ai.py`; checking and saving
  through the tab's own `save_*` go in `extract.py`.

**JS: `ui/daylog.js`**

- **`dayBar`:** date navigation.
- **`dayBox`:** a day's text box, with a + menu of templates.
- **`weightBox`:** the day's weight.
- **`diaryDay`:** a past day's note beside its data, with "Edit note" and
  "Edit data".
- **`dayFlush`:** saves anything still being typed.

**JS: `ui/templates.js` and `ui/app.js`**

- **`ui/templates.js`:** the Templates view (`templatesRender`).
- **`ui/app.js`:**
  - building elements: `el`, `icon`
  - menus and pickers: `openMenu`, `openDatePicker`, `showPopover`
  - messages and buttons: `showToast`, `deleteButton` (click twice to delete)
  - redrawing while typing: `keepingFocus`
  - formatting: `fmtNumber`, `fmtDay`, `dateLabel`
  - date maths: `today`, `addDays`, `mondayOf`
  - AI extraction: `extractPending`, `showExtractButton`

**CSS:** reuse the existing classes (`data-table compact`, `edit-table`,
`set-input`, `pane-header`, `sidebar`/`nav-item`, `session`, `text-button`,
`primary-button`, `icon-button`) so new tabs look the same.

---

## Adding a new tab

Say the tab is called **Sleep** (`sleep`):

1. **`schema/sleep.sql`.** Write its tables, with the comments that the README
   is generated from:
   - a header comment: `-- Sleep: what the tab keeps.`
   - a comment above each table;
   - a trailing comment on every column that needs one.

   Add `"sleep.sql"` to `db.SCHEMA_FILES`.
2. **`app/tabs/sleep.py`.** Plain functions that take `conn` and return dicts
   and lists:
   - Check inputs and raise `ValueError` with a readable message.
   - Write inside `with conn:`.
   - Put the module docstring at the top: what the tab owns and why.
3. **`app/api.py`.** Add a `# --- Sleep ---` group of thin
   `sleep_<action>` methods.
4. **`ui/index.html`.**
   - Add a `<button class="tab" data-tab="sleep">` before the spacer in the
     tab bar.
   - Add a `<section id="tab-sleep" class="tab-panel" hidden>`, with a
     sidebar if it has several views.
   - Add `<script src="tabs/sleep.js">` after the other tab scripts.
5. **`ui/tabs/sleep.js`.**
   - A state object and a load function that calls the API.
   - Draw with `el()`.
   - Reload when shown:
     `document.addEventListener("tabshown", (e) => { if (e.detail === "sleep") sleepLoad(); });`
6. **If it belongs in the Overview,** add it to `app/tabs/log.py` (read
   through `sleep.py`'s functions) and `ui/tabs/log.js` (save through
   `sleep_save_*`).
7. **If it keeps text files,** give them a folder function that follows
   `db.DATA_DIR` (see `journal.folder()`), and add the folder to the
   backups in `datafolder.open_folder`. Describe them in
   `datadoc.TEXT_FILES`.
8. **`tests/test_sleep.py`.** Test the Python functions using the `conn`
   fixture.
9. **`mock_data.py`.** Add some data, so the test folder shows the new tab.
10. **This README.** Update the tabs table and the layout.

Do it as small steps, each one leaving the app working: tables and Python
with tests first, then the UI.

## Adding a feature or changing tables

- **New behaviour:** put the logic and its checks in the tab's Python
  module, with a test. The API method stays a one-line wrapper. The UI only
  draws and calls.
- **Changing tables:**
  1. Edit `schema/<tab>.sql` in place, with its comments.
  2. Update the tab module, `mock_data.py` and the tests.
  3. Open the app on *Test data*; it rebuilds itself to match.
  4. If my own data exists in the old shape, a
     [conversion script](#conversion-scripts-step-3) is part of the change.
- **AI changes:**
  - The response shape is the pydantic models in `ai.py`.
  - The wording is `DEFAULT_PROMPTS`, and the live copy is in the data
    folder's `AI Prompts/`.
  - Check prompt changes with the live tests.
- **Before calling it done:**
  - `pytest` passes.
  - The change has been tried in the app on *Test data*.
  - `mock_data.py` shows it.
  - The schema comments are current.
  - This README is current, if the change affects layout, workflow or
    conventions.

---

## Code conventions

- **Code should read like the code around it:** short functions, a docstring
  saying what and why, and comments only where something isn't obvious.
- **Python:** standard library first; f-strings; `pathlib`. User-facing
  messages are plain English, e.g. `"This exercise has sets logged, so it
  can't be deleted"`.
- **SQL:** parameters with `?`. Table names are never built from user input
  (see `daylog._table`).
- **JS:**
  - Functions are named with the tab as a prefix (`gymLoad`,
    `foodRenderDiary`), because all scripts share one global scope.
  - `async`/`await`.
  - No frameworks and no `innerHTML` with data.
- **Edits in place:** inputs save on `change`; Enter blurs the input. A
  refused value goes back to the old one, and a toast explains why.
- **Deleting:** anything deleted for good takes two clicks
  (`deleteButton`). To Do tasks go to Recently deleted instead.
- **Files are written all-or-nothing:** write a `.tmp` file, then
  `os.replace` it.
- **Look:** minimal design, light and dark mode from the CSS variables, and
  macOS system fonts.

---

## Rules for AI agents

- **`../LifeOS_data` is my real data. Never test against it:**
  - don't run `mock_data.py` against it;
  - don't open it from scripts;
  - don't delete or reset anything in it.

  The only exception is a conversion script I've asked for, run when I say
  so.
- **Test on throwaway folders:**
  - For your own checks, set `LIFEOS_DATA_DIR` to a temp folder before
    importing the app (the tests already do this).
  - When the folder is set this way, Settings can't switch it, and
    `data_folder.txt` is never read or written.
- **UI changes:**
  - Check them on test data or a temp folder. A headless browser serving
    `ui/` with a small stand-in for `window.pywebview.api` that forwards to
    `Api` over HTTP works well.
  - Don't leave such tools in the repo unless asked.
- **Step by step:** make one step at a time, keep the app working, and
  explain what changed and why, briefly and in plain words. Ask before big
  restructures or new dependencies.
- **Keep it simple:** while data is mock data, don't add complexity to
  preserve it.
- **Keep docs current:** update `schema/` comments, `datadoc.TEXT_FILES` and
  this README when what they describe changes.
- **Git:** never commit `.env`, `test_data/`, `data_folder.txt` or anything
  from `LifeOS_data`. Commit only when asked.

---

## Ideas not built yet

- Delete or move a whole day in the Gym and Food diaries.
- Body: blood test reports.
- A "Data" view per tab: every table in full, every cell editable.
- Views over time: exercise progress, calories and macros by week, weight
  trend.
- Mobile: not planned for now (desktop only).
