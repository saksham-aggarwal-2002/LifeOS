// Journal tab: Journal owns its daily log (one text file per day), so it starts
// with the Journal box for one day (the same box as in the Overview), then
// every day's entry, newest first, so all of it is visible in one place.
const journalState = { day: today() };

async function journalLoad() {
  const entries = await call("journal_get_all");
  $("journal-subtitle").textContent = entries.length
    ? `${entries.length} entr${entries.length === 1 ? "y" : "ies"}` : "";
  $("journal-entries").replaceChildren(...entries.map((entry) => el("article", { class: "session" },
    el("div", { class: "session-head" },
      el("span", { class: "session-day" }, fmtDay(entry.day)),
      el("span", { class: "session-actions" },
        el("button", { class: "text-button", onclick: () => journalEditDay(entry.day) }, "Edit"),
      ),
    ),
    el("pre", { class: "gym-source-text journal-text" }, entry.body),
  )));
}

// The Journal box: the day's text, saved by journal_save_day like the Overview's.
async function journalLoadDay() {
  await dayFlush();
  const text = await call("journal_get_day", journalState.day);
  $("journal-daylog").replaceChildren(
    dayBar(journalState.day, (day) => { journalState.day = day; journalLoadDay(); }, { small: true }),
    dayBox({ kind: "journal", label: "Journal", day: journalState.day, text, save: "journal_save_day",
             onSaved: journalLoad }),
  );
}

// "Edit" on a past day: open it in the Journal box at the top.
function journalEditDay(day) {
  journalState.day = day;
  journalLoadDay();
  $("journal-daylog").scrollIntoView({ behavior: "smooth" });
}

document.addEventListener("tabshown", (e) => { if (e.detail === "journal") journalLoad().then(journalLoadDay); });
