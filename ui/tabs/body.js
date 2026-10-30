// Body tab: health metrics over time, one sidebar view each.
//   "weight"  the weight box for one day (the same box as in the Overview),
//             then the weights table: every weigh-in, newest first
const bodyState = { view: "weight", day: today() };

async function bodyLoad() {
  const weights = await call("body_get_weights");
  $("body-subtitle").textContent = weights.length
    ? `${weights.length} weigh-in${weights.length === 1 ? "" : "s"}` : "";
  $("body-weight").replaceChildren(...(weights.length ? [
    el("table", { class: "data-table compact weight-table" },
      el("thead", {}, el("tr", {}, el("th", {}, "Day"), el("th", { class: "num" }, "kg"))),
      el("tbody", {}, ...weights.map((w) => el("tr", {},
        el("td", { class: "nowrap" }, el("button", { class: "link-button", title: "Edit", onclick: () => bodyEditDay(w.day) }, fmtDay(w.day))),
        el("td", { class: "num" }, fmtNumber(w.kg, 2)),
      ))),
    ),
  ] : []));
}

// The weight box: the day's weight, saved by body_save_weight like the Overview's.
async function bodyLoadDay() {
  await dayFlush();
  const kg = await call("body_get_weight", bodyState.day);
  $("body-daylog").replaceChildren(
    dayBar(bodyState.day, (day) => { bodyState.day = day; bodyLoadDay(); }, { small: true }),
    weightBox(bodyState.day, kg, { onSaved: bodyLoad }),
  );
}

// Clicking a past day opens it in the weight box at the top.
function bodyEditDay(day) {
  bodyState.day = day;
  bodyLoadDay();
  $("body-daylog").scrollIntoView({ behavior: "smooth" });
}

document.addEventListener("tabshown", (e) => { if (e.detail === "body") bodyLoad().then(bodyLoadDay); });
