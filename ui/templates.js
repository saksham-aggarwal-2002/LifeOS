// Templates view, shared by Gym (workouts) and Food (recipes): a list of
// names beside the selected one's text. Each template is a text file
// (app/templates.py), known by its name; typing saves after a short pause.

// tab ("Gym" | "Food") -> { list: [{ name, body, file }], selected }
// `file` is the name on disk, `name` what's typed (they differ until saved).
const templatesState = { Gym: { list: [], selected: null }, Food: { list: [], selected: null } };

// --- Saving: one save at a time, so a rename finishes before the next edit ---

const templatesPending = new Set();
let templatesSaving = Promise.resolve();

function templatesFlush() {
  templatesSaving = templatesSaving.then(async () => {
    const pending = [...templatesPending];
    templatesPending.clear();
    for (const t of pending) {
      try {
        t.file = await call("templates_save", t.tab, t.file, t.name, t.body);
      } catch (err) {
        showToast(err.message || String(err));
      }
    }
  });
  return templatesSaving;
}
const templatesSaveSoon = debounce(templatesFlush, 500);
window.addEventListener("beforeunload", () => templatesFlush());

async function templatesLoad(tab) {
  await templatesFlush();
  const state = templatesState[tab];
  state.list = (await call("templates_get", tab)).map((t) => ({ ...t, tab, file: t.name }));
  state.selected = state.list.find((t) => t.file === state.selected?.file) ?? null;
  return state.list;
}

// What a day box's + offers: the name as a heading, then the text.
const templateItems = (list) => list.map((t) => ({ label: t.name, text: t.body ? `${t.name}\n${t.body}` : t.name }));

// --- Drawing ---

// newLabel: "+ New workout"; placeholder: a hint for an empty template's text.
function templatesRender(tab, box, { newLabel, placeholder }) {
  const state = templatesState[tab];
  const redraw = () => templatesRender(tab, box, { newLabel, placeholder });

  const input = el("input", { class: "add-input", placeholder: newLabel, maxlength: "100" });
  const form = el("form", {}, input);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!input.value.trim()) return;
    try {
      const name = await call("templates_create", tab, input.value);
      await templatesLoad(tab);
      state.selected = state.list.find((t) => t.file === name);
    } catch (err) {
      showToast(err.message || String(err));
      return;
    }
    redraw();
    box.querySelector(".workout-body")?.focus();
  });

  const items = state.list.map((t) => el("button", {
    class: t === state.selected ? "nav-item active" : "nav-item",
    onclick: () => { state.selected = t; redraw(); },
  }, t.name));

  box.replaceChildren(
    el("div", { class: "workout-list" }, form, el("div", {}, ...items)),
    el("div", { class: "workout-editor" }, ...(state.selected ? templateEditor(state.selected, items[state.list.indexOf(state.selected)], redraw, placeholder) : [])),
  );
}

function templateEditor(t, listItem, redraw, placeholder) {
  const state = templatesState[t.tab];
  const name = el("input", { class: "workout-name", value: t.name, maxlength: "100" });
  const body = el("textarea", { class: "workout-body", placeholder });
  body.value = t.body;

  const changed = () => {
    if (name.value.trim()) t.name = name.value.trim();  // a name is required; keep the old one while empty
    t.body = body.value;
    listItem.textContent = t.name;
    templatesPending.add(t);
    templatesSaveSoon();
  };
  name.addEventListener("input", changed);
  body.addEventListener("input", changed);

  // Two clicks, like everything else that deletes for good.
  const del = deleteButton(async () => {
    templatesPending.delete(t);
    await templatesFlush();
    await call("templates_delete", t.tab, t.file);
    state.list = state.list.filter((x) => x !== t);
    state.selected = null;
    redraw();
  });
  return [el("div", { class: "workout-editor-head" }, name, del), body];
}
