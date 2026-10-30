// Gym tab: Gym owns its daily log, so "Gym Diary" starts with the Gym box
// for one day (the same box as in the Overview), then every day logged.
//   "all"        a day's Gym box, then every workout entry, newest first: the
//                text beside the structured data extracted from it
//   "exercises"  the exercises library: add, rename in place, delete unused;
//                each with how often, when last and its best set
//   "templates"  workout templates (text files) for the Gym box's +: ui/templates.js
const gym = {
  view: "all",          // "all" | "exercises" | "templates"
  day: today(),         // the day in the Gym box
  sessions: [],
  exercises: [],        // the library: [{ id, exercise, sessions, last_day, top }]
  editing: null,        // entry id whose structured data is being edited
  draft: [],            // its sets while editing (saved only on Save)
};

// --- Data ---

async function gymLoad() {
  [gym.exercises, , gym.sessions] = await Promise.all([
    gym.view === "exercises" || gym.view === "all" ? call("gym_get_exercises") : [],
    templatesLoad("Gym"),
    gym.view === "all" ? call("gym_get_sessions") : [],
  ]);
  gymRender();
}

// The Gym box: the day's text, saved by gym_save_day like the Overview's.
async function gymLoadDay() {
  await dayFlush();
  const text = await call("gym_get_day", gym.day);
  $("gym-daylog").replaceChildren(
    dayBar(gym.day, (day) => { gym.day = day; gymLoadDay(); }, { small: true }),
    dayBox({ kind: "gym", label: "Gym", day: gym.day, text, save: "gym_save_day",
             templates: templateItems(templatesState.Gym.list), addTitle: "Add a template",
             onSaved: () => { if (gym.view === "all") gymLoad(); } }),
  );
}

// "Edit" on a past day: open it in the Gym box at the top.
function gymEditDay(day) {
  gym.day = day;
  gymLoadDay();
  $("gym-daylog").scrollIntoView({ behavior: "smooth" });
}

async function gymSelect(view) {
  gym.view = view;
  gym.editing = null;
  gymLoad().then(() => { if (view === "all") gymLoadDay(); });  // templates may have changed
}

// --- Formatting ---

const fmtWeight = (s) => (s.weight == null ? "BW" : fmtNumber(s.weight, 2));  // kg; none = bodyweight
const fmtSet = (s) => `${fmtWeight(s)} × ${s.reps}`;

// --- Drawing ---

function gymRender() {
  const view = gym.view;
  document.querySelectorAll("#tab-gym .sidebar .nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === view);
  });

  $("gym-all").hidden = view !== "all";
  $("gym-daylog").hidden = view !== "all";
  $("gym-exercises").hidden = view !== "exercises";
  $("gym-templates").hidden = view !== "templates";

  showExtractButton($("gym-extract"), view === "all", gym.sessions);
  if (view === "all") {
    $("gym-title").textContent = "Gym Diary";
    $("gym-subtitle").textContent = gym.sessions.length ? `${gym.sessions.length} logged` : "";
    gymRenderAll();
  } else if (view === "exercises") {
    $("gym-title").textContent = "Exercises";
    $("gym-subtitle").textContent = gym.exercises.length ? `${gym.exercises.length} in your library` : "";
    gymRenderExercises();
  } else {
    $("gym-title").textContent = "Templates";
    $("gym-subtitle").textContent = "";
    templatesRender("Gym", $("gym-templates"), { newLabel: "+ New workout", placeholder: "Bench press: kg :\nPull ups:" });
  }
}

// Every day in the Gym Diary: its text beside the sets extracted from it.
function gymRenderAll() {
  $("gym-all").replaceChildren(...gym.sessions.map((session) => {
    const editing = gym.editing === session.id;
    return diaryDay({
      day: session.day, status: session.status, body: session.body, editing,
      data: editing ? gymSetEditor(session) : gymSetsTable(session),
      onEditNote: () => gymEditDay(session.day),
      onEditData: () => gymStartEditing(session),
    });
  }));
}

// A day's sets in full: the same columns as Edit data, plus each set's number.
function gymSetsTable(session) {
  if (!session.exercises.length) return el("p", { class: "muted diary-empty" }, "No sets yet");
  return el("div", { class: "table-scroll" }, el("table", { class: "data-table compact sets-table" },
    el("thead", {}, el("tr", {},
      el("th", {}, "Exercise"), el("th", { class: "num" }, "Set"), el("th", { class: "num" }, "Weight (kg)"),
      el("th", { class: "num" }, "Reps"), el("th", {}, "Note"),
    )),
    el("tbody", {}, ...session.exercises.flatMap((x) => x.sets.map((s, i) => el("tr", { class: i ? "" : "first-set" },
      el("td", { class: "exercise-cell" }, ...(i ? [] : [x.exercise])),
      el("td", { class: "num muted" }, s.set_no),
      el("td", { class: "num" }, s.weight == null ? el("span", { class: "muted" }, "BW") : fmtNumber(s.weight, 2)),
      el("td", { class: "num" }, s.reps),
      el("td", { class: "muted" }, s.note),
    )))),
  ));
}

// --- Editing structured data by hand ---

const SET_FIELDS = ["exercise", "weight", "reps", "note"];

function gymStartEditing(session) {
  gym.editing = session.id;
  gym.draft = session.exercises.flatMap((x) => x.sets.map((s) =>
    Object.fromEntries(SET_FIELDS.map((f) => [f, s[f] ?? ""]))));
  if (!gym.draft.length) gym.draft.push(gymBlankSet());
  gymRenderAll();
  document.querySelector(".set-editor input")?.focus();
}

// A new set copies the previous one's exercise and weight: most rows in a
// session differ only in reps. An empty weight is bodyweight.
function gymBlankSet(previous) {
  return { exercise: previous?.exercise ?? "", weight: previous?.weight ?? "", reps: "", note: "" };
}

function gymStopEditing() {
  gym.editing = null;
  gym.draft = [];
  gymRenderAll();
}

async function gymSaveDraft() {
  const sets = gym.draft.filter((s) => SET_FIELDS.some((f) => String(s[f]).trim() !== ""));
  try {
    await call("gym_save_sets", gym.editing, sets);
  } catch (err) {
    showToast(err.message || String(err));
    return;
  }
  gym.editing = null;
  gym.draft = [];
  gymLoad();
}

function gymSetEditor(session) {
  const cell = (s, field, attrs = {}) => el("td", {}, el("input", {
    class: `set-input ${field}`, value: s[field] ?? "", ...attrs,
    oninput: (e) => { s[field] = e.target.value; },
  }));
  const num = (s, field, step, placeholder = "") => cell(s, field, { type: "number", min: "0", step, placeholder });
  const addSet = () => {
    gym.draft.push(gymBlankSet(gym.draft.at(-1)));
    gymRenderAll();
    document.querySelector(".set-editor tbody tr:last-child .reps")?.focus();
  };

  return el("div", {
    class: "set-editor",
    onkeydown: (e) => {
      if (e.key === "Escape") gymStopEditing();
      else if (e.key === "Enter" && e.metaKey) gymSaveDraft();
      else if (e.key === "Enter" && e.target.tagName === "INPUT") addSet();
    },
  },
    el("datalist", { id: "gym-exercise-names" }, ...gym.exercises.map((x) => el("option", { value: x.exercise }))),
    el("table", { class: "data-table compact" },
      el("thead", {}, el("tr", {},
        el("th", {}, "Exercise"), el("th", {}, "Weight (kg)"), el("th", {}, "Reps"),
        el("th", {}, "Note"), el("th", {}),
      )),
      el("tbody", {}, ...gym.draft.map((s, i) => el("tr", {},
        cell(s, "exercise", { list: "gym-exercise-names" }),
        num(s, "weight", "any", "BW"), num(s, "reps", "1"), cell(s, "note"),
        el("td", {}, el("button", {
          class: "icon-button", title: "Remove set",
          onclick: () => { gym.draft.splice(i, 1); gymRenderAll(); },
        }, icon("trash"))),
      ))),
    ),
    el("div", { class: "set-editor-actions" },
      el("button", { class: "text-button", onclick: addSet }, "+ Add set"),
      el("span", { class: "spacer" }),
      el("button", { class: "text-button", onclick: gymStopEditing }, "Cancel"),
      el("button", { class: "primary-button", onclick: gymSaveDraft }, "Save"),
    ),
  );
}

// The exercises library: every exercise, how often and how recently you've
// done it, and your best. Add one before doing it, rename it in its box (every
// past set changes too), or delete one you've never done.
function gymRenderExercises() {
  const add = el("form", { class: "exercise-add" },
    el("input", { class: "add-input", placeholder: "+ New exercise", maxlength: "100" }));
  add.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = add.querySelector("input").value;
    if (!name.trim()) return;
    if (await gymTry(() => call("gym_add_exercise", name))) await gymLoad();
    $("gym-exercises").querySelector(".exercise-add input")?.focus();
  });

  $("gym-exercises").replaceChildren(add, ...(gym.exercises.length ? [el("div", { class: "table-scroll" }, el("table", { class: "data-table compact edit-table exercise-table" },
    el("thead", {}, el("tr", {},
      el("th", {}, "Exercise"), el("th", { class: "num" }, "Sessions"), el("th", { class: "num" }, "Last done"),
      el("th", { class: "num" }, "Best"), el("th", {}),
    )),
    el("tbody", {}, ...gym.exercises.map((x) => el("tr", {},
      el("td", {}, gymNameInput(x)),
      el("td", { class: "num" }, x.sessions ? fmtNumber(x.sessions) : ""),
      el("td", { class: "num" }, x.last_day ? fmtDay(x.last_day) : "Not done yet"),
      el("td", { class: "num" }, x.top ? fmtSet(x.top) : ""),
      // Only one you've never done can go: past sets need their exercise.
      el("td", {}, ...(x.sessions ? [] : [deleteButton(async () => { await call("gym_delete_exercise", x.id); gymLoad(); })])),
    ))),
  ))] : []));
}

// The name, edited in place like a food's: leaving the box (or Enter) renames
// it everywhere; a name that's refused goes back to the old one.
function gymNameInput(x) {
  const input = el("input", {
    class: "set-input", maxlength: "100", "data-key": `exercise-${x.id}`,
    onchange: async (e) => {
      try {
        await call("gym_rename_exercise", x.id, e.target.value);
        x.exercise = e.target.value.trim();
      } catch (err) {
        e.target.value = x.exercise;
        showToast(err.message || String(err));
      }
    },
    onkeydown: (e) => { if (e.key === "Enter") e.target.blur(); },
  });
  input.value = x.exercise;
  return input;
}

// Runs a call; on refusal shows why and returns false.
async function gymTry(fn) {
  try {
    await fn();
    return true;
  } catch (err) {
    showToast(err.message || String(err));
    return false;
  }
}

// --- Events ---

document.querySelectorAll("#tab-gym .sidebar > .nav-item").forEach((item) => {
  item.addEventListener("click", () => gymSelect(item.dataset.view));
});

$("gym-extract").addEventListener("click", () =>
  extractPending($("gym-extract"), gym.sessions, "extract_workout", "workouts", gymLoad));

document.addEventListener("tabshown", (e) => (e.detail === "gym" ? gymLoad().then(gymLoadDay) : templatesFlush()));

gymLoad().then(gymLoadDay);
