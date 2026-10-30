// Shared helpers and tab switching. Each tab's own code lives in ui/tabs/.

// Calls a Python method on app/api.py's Api class, e.g. call("todo_get_lists").
// pywebview injects window.pywebview.api once it's ready; wait for that first.
const pywebviewReady = new Promise((resolve) => {
  if (window.pywebview?.api) resolve();
  else window.addEventListener("pywebviewready", resolve, { once: true });
});

async function call(method, ...args) {
  await pywebviewReady;
  return window.pywebview.api[method](...args);
}

const $ = (id) => document.getElementById(id);

// Builds an element: el("button", { class: "x", onclick: fn }, "text", child)
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null) continue;  // leave the attribute off
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}

// Tab switching: show the section matching the clicked tab, hide the rest.
// Tabs share data (e.g. ticking a task in the Overview changes To Do), so each
// tab listens for "tabshown" and reloads itself when it appears.
document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    const name = button.dataset.tab;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === button));
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.hidden = panel.id !== `tab-${name}`;
    });
    document.dispatchEvent(new CustomEvent("tabshown", { detail: name }));
  });
});

// Grow a textarea to fit its text.
function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

// --- Dates: 'YYYY-MM-DD' strings in local time, same format as Python ---

function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function addDays(iso, n) {
  const d = parseDate(iso);
  d.setDate(d.getDate() + n);
  return isoDate(d);
}

const today = () => isoDate(new Date());

// "Today", "Tomorrow", "Wed 28 Oct", or "Overdue · Fri 23 Oct" for an open task.
function dateLabel(iso, completed) {
  const t = today();
  if (iso === t) return "Today";
  if (iso === addDays(t, 1)) return "Tomorrow";
  const pretty = parseDate(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  return iso < t && !completed ? `Overdue · ${pretty}` : pretty;
}

// The Monday on or before a date.
function mondayOf(iso) {
  return addDays(iso, -((parseDate(iso).getDay() + 6) % 7));
}

// "26 Oct – 1 Nov 2026" for the week starting on `monday`.
function weekLabel(monday) {
  const fmt = (iso, opts) => parseDate(iso).toLocaleDateString("en-GB", opts);
  return `${fmt(monday, { day: "numeric", month: "short" })} – ${fmt(addDays(monday, 6), { day: "numeric", month: "short", year: "numeric" })}`;
}

// --- Formatting numbers and days for display ---

const fmtNumber = (n, digits = 0) => (n ?? 0).toLocaleString("en-GB", { maximumFractionDigits: digits });
const fmtDay = (iso) => parseDate(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

// Redraw something you may be typing in without losing your place: inputs
// carry a data-key, and focus + cursor return to the input with the same key.
function keepingFocus(draw) {
  const active = document.activeElement;
  const key = active?.dataset?.key;
  let start = null, end = null;
  try { start = active.selectionStart; end = active.selectionEnd; } catch {}  // number inputs have no selection
  draw();
  if (!key) return;
  const again = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
  if (!again) return;
  again.focus();
  try { if (start != null) again.setSelectionRange(start, end); } catch {}
}

// Debounce: run fn only after `ms` without another call (used for autosave).
function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

// Trash icon that needs a second click, for things deleted for good.
// If onDelete fails (e.g. Python refuses), the reason shows as a toast.
function deleteButton(onDelete) {
  const button = el("button", { class: "icon-button", title: "Delete" }, icon("trash"));
  button.addEventListener("click", async () => {
    if (!button.dataset.armed) {
      button.dataset.armed = "1";
      button.classList.add("danger");
      button.title = "Click again to delete";
      return;
    }
    try {
      await onDelete();
    } catch (err) {
      showToast(err.message || String(err));
    }
  });
  return button;
}

// --- Icons: small line drawings that take the text colour ---

const ICONS = {
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  calendar: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M3 12h2M19 12h2M5.6 18.4 7 17M17 7l1.4-1.4"/>',
  restore: '<path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6"/><path d="M4 4v4.6h4.6"/>',
};

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.innerHTML = ICONS[name];
  return svg;
}

// --- Popovers: one at a time, opened under a button, closed by clicking
// elsewhere or Esc. Buttons that open one get the class "opens-popover". ---

let popoverEl = null;

function showPopover(anchor, popover) {
  closePopover();
  document.body.append(popover);
  popoverEl = popover;
  // Place it under the button, or above if there's no room below.
  const a = anchor.getBoundingClientRect();
  const p = popover.getBoundingClientRect();
  const top = a.bottom + 6 + p.height > innerHeight ? a.top - 6 - p.height : a.bottom + 6;
  popover.style.top = `${Math.max(8, top)}px`;
  popover.style.left = `${Math.max(8, Math.min(a.left, innerWidth - p.width - 8))}px`;
}

function closePopover() {
  popoverEl?.remove();
  popoverEl = null;
}

document.addEventListener("mousedown", (e) => {
  if (popoverEl && !popoverEl.contains(e.target) && !e.target.closest(".opens-popover")) closePopover();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePopover(); });

// A menu of choices: items are { label, onClick }, { heading } for a small
// section title, or "-" for a divider. { indent: true } indents an item.
function openMenu(anchor, items) {
  const menu = el("div", { class: "popover menu" },
    ...items.map((item) => {
      if (item === "-") return el("div", { class: "menu-divider" });
      if (item.heading) return el("div", { class: "menu-heading" }, item.heading);
      const classes = ["menu-item", item.muted && "muted", item.indent && "indent"].filter(Boolean);
      return el("button", { class: classes.join(" "), onclick: () => { closePopover(); item.onClick(); } }, item.label);
    }),
  );
  showPopover(anchor, menu);
}

// --- Date picker ---

// onPick receives 'YYYY-MM-DD', or null for "Clear".
function openDatePicker(anchor, value, onPick) {
  let month = (value || today()).slice(0, 8) + "01";  // month being shown

  const pick = (iso) => { closePopover(); onPick(iso); };
  const popover = el("div", { class: "popover date-picker" });

  function draw() {
    const shift = (n) => { const d = parseDate(month); d.setMonth(d.getMonth() + n); month = isoDate(d); draw(); };
    const title = parseDate(month).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
    const days = [];
    for (let d = mondayOf(month); days.length < 42; d = addDays(d, 1)) days.push(d);

    popover.replaceChildren(
      el("div", { class: "dp-head" },
        el("button", { class: "icon-button", onclick: () => shift(-1) }, "‹"),
        el("span", {}, title),
        el("button", { class: "icon-button", onclick: () => shift(1) }, "›"),
      ),
      el("div", { class: "dp-grid" },
        ...["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => el("span", { class: "dp-weekday" }, d)),
        ...days.map((d) => {
          const classes = ["dp-day"];
          if (d.slice(0, 7) !== month.slice(0, 7)) classes.push("other-month");
          if (d === today()) classes.push("today");
          if (d === value) classes.push("selected");
          return el("button", { class: classes.join(" "), onclick: () => pick(d) }, String(parseDate(d).getDate()));
        }),
      ),
      el("div", { class: "dp-foot" },
        el("button", { class: "text-button", onclick: () => pick(today()) }, "Today"),
        el("button", { class: "text-button", onclick: () => pick(addDays(today(), 1)) }, "Tomorrow"),
        ...(value ? [el("button", { class: "text-button", onclick: () => pick(null) }, "Clear")] : []),
      ),
    );
  }
  draw();
  showPopover(anchor, popover);
}

// --- Extract Structured Data: AI, one entry at a time, with progress ---

// entries: [{ id, day, status }]. Sends every not-analysed or changed one to
// `method` (extract_workout / extract_food), then reports what happened.
async function extractPending(button, entries, method, noun, done) {
  const pending = entries.filter((e) => e.status !== "analysed");
  if (!pending.length || button.disabled) return;
  const label = button.textContent;
  button.disabled = true;
  const failed = [];
  for (const [i, entry] of pending.entries()) {
    button.textContent = `Extracting ${i + 1} of ${pending.length}…`;
    try {
      await call(method, entry.id);
    } catch (err) {
      failed.push(`${fmtDay(entry.day)}: ${err.message || err}`);
    }
  }
  button.textContent = label;
  button.disabled = false;
  await done();
  const ok = pending.length - failed.length;
  showToast(failed.length
    ? `Extracted ${ok} of ${pending.length} ${noun}. ${failed.join(" · ")}`
    : `Extracted ${ok} ${noun}`);
}

// Show the button on its view; enabled only when something needs extracting.
function showExtractButton(button, visible, entries) {
  button.hidden = !visible;
  const count = entries.filter((e) => e.status !== "analysed").length;
  if (button.textContent.startsWith("Extracting")) return;  // still running
  button.disabled = !count;
  button.title = count ? `${count} to extract` : "Everything is extracted";
}

// --- Toast: a short message at the bottom with an optional action (e.g. Undo) ---

let toastTimer = null;

function showToast(message, actionLabel, onAction) {
  document.querySelector(".toast")?.remove();
  clearTimeout(toastTimer);
  const toast = el("div", { class: "toast" }, el("span", {}, message));
  if (actionLabel) {
    toast.append(el("button", { class: "toast-action", onclick: () => { toast.remove(); onAction(); } }, actionLabel));
  }
  document.body.append(toast);
  toastTimer = setTimeout(() => toast.remove(), 6000);
}
