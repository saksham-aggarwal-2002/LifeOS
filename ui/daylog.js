// Daily-log pieces shared by the Overview and the tabs that own the data
// (Gym, Food, Journal, Body): a date bar, a text box and the weight box. Each
// saves straight to its tab (gym_save_day, ...), so typing the same day in the
// Overview or in the tab changes the same thing.

// --- Saving: typing saves after a short pause; changing day or tab saves
// anything still pending first (await dayFlush() before loading a day). ---

// key "method|day" -> { method, day, value, onSaved, onError }
const dayPending = new Map();

async function dayFlush() {
  const pending = [...dayPending.values()];
  dayPending.clear();
  await Promise.all(pending.map(async (p) => {
    try {
      await call(p.method, p.day, p.value);
      p.onSaved?.();
    } catch (err) {
      p.onError?.(err.message || String(err));
    }
  }));
}
const daySaveSoon = debounce(dayFlush, 500);

function daySave(method, day, value, { onSaved, onError } = {}) {
  dayPending.set(`${method}|${day}`, { method, day, value, onSaved, onError });
  daySaveSoon();
}

window.addEventListener("beforeunload", () => dayFlush());

// --- Date bar: ‹ Today › and a calendar, above the day's date ---

const longDate = (day) => parseDate(day).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const nearLabel = (day) => ({ [today()]: "Today", [addDays(today(), -1)]: "Yesterday", [addDays(today(), 1)]: "Tomorrow" })[day] ?? "";

// onChange(newDay) is called after pending text has saved. `small` for a
// tab's bar (the Overview's date is the page heading).
function dayBar(day, onChange, { small = false } = {}) {
  const go = async (next) => { await dayFlush(); onChange(next); };
  const pick = el("button", { class: "icon-button opens-popover", title: "Go to date" }, icon("calendar"));
  pick.addEventListener("click", () => openDatePicker(pick, day, (d) => go(d || today())));
  const todayButton = el("button", { class: "text-button", onclick: () => go(today()) }, "Today");
  todayButton.disabled = day === today();
  return el("header", { class: small ? "day-header small" : "day-header" },
    el("div", { class: "cal-nav" },
      pick,
      el("button", { class: "icon-button", title: "Previous day", onclick: () => go(addDays(day, -1)) }, "‹"),
      todayButton,
      el("button", { class: "icon-button", title: "Next day", onclick: () => go(addDays(day, 1)) }, "›"),
    ),
    el("div", { class: "day-heading" },
      el(small ? "h2" : "h1", { class: "day-title" }, longDate(day)),
      el("span", { class: "day-near" }, nearLabel(day)),
    ),
  );
}

// --- Text box: one tab's free text for one day ---

// kind: "gym" | "food" | "journal" (colour), save: the tab's save method,
// templates: what + offers, [{ label, text }] (templateItems in ui/templates.js).
// onSaved runs after each save, e.g. so a tab can refresh its history.
function dayBox({ kind, label, day, text, save, templates = [], addTitle, onSaved }) {
  const body = el("textarea", { class: "log-entry-body", rows: "3" });
  body.value = text ?? "";

  const changed = () => {
    autoGrow(body);
    daySave(save, day, body.value, { onSaved });
  };
  body.addEventListener("input", changed);
  requestAnimationFrame(() => autoGrow(body));

  const add = el("button", { class: "add-button small opens-popover", title: addTitle }, "+");
  add.addEventListener("click", () => openMenu(add, templates.map((t) => ({
    label: t.label,
    onClick: () => {
      // Add on a new line at the end, then carry on typing after it.
      const current = body.value.replace(/\s+$/, "");
      body.value = (current ? `${current}\n` : "") + t.text.replace(/\s+$/, "") + "\n";
      changed();
      body.focus();
      body.setSelectionRange(body.value.length, body.value.length);
    },
  }))));

  return el("div", { class: `log-entry kind-${kind}` },
    el("div", { class: "log-entry-head" }, el("span", { class: "log-kind" }, label)),
    body,
    ...(templates.length ? [el("div", { class: "log-entry-foot" }, add)] : []),
  );
}

// --- A past day in Gym's or Food's diary ---

// The day's note beside its structured data, each with its own button above
// it: "Edit note" opens the day in the box at the top, "Edit data" the data
// editor (hidden while it's open: the editor has Save and Cancel).
function diaryDay({ day, status, body, data, onEditNote, onEditData, editing }) {
  const part = (button, content) => el("div", { class: "diary-part" },
    el("div", { class: "diary-part-head" }, ...(button ? [button] : [])), content);
  return el("article", { class: "session" },
    el("div", { class: "session-head" },
      el("span", { class: "session-day" }, fmtDay(day)),
      ...(STATUS_LABELS[status] ? [el("span", { class: `status-tag ${status}` }, STATUS_LABELS[status])] : []),
    ),
    el("div", { class: editing ? "session-body editing" : "session-body" },
      part(el("button", { class: "text-button", onclick: onEditNote }, "Edit note"),
           el("pre", { class: "gym-source-text" }, body)),
      part(editing ? null : el("button", { class: "text-button", onclick: onEditData }, "Edit data"), data),
    ),
  );
}

const STATUS_LABELS = { not_analysed: "Not analysed", changed: "Changed since analysis" };

// --- Weight box: Body's weight for one day, in kg ---

function weightBox(day, kg, { onSaved } = {}) {
  const error = el("span", { class: "weight-error" });
  const input = el("input", { class: "weight-input", inputmode: "decimal", placeholder: "–" });
  input.value = kg ?? "";
  // A weight Python refuses (e.g. 0) shows why beside the box instead of saving.
  input.addEventListener("input", () => daySave("body_save_weight", day, input.value, {
    onSaved: () => { error.textContent = ""; onSaved?.(); },
    onError: (message) => { error.textContent = message; },
  }));
  return el("label", { class: "log-entry kind-body weight-box" },
    el("span", { class: "log-kind" }, "Weight"),
    input,
    el("span", { class: "muted" }, "kg"),
    error,
  );
}
