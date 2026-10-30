// Overview tab (internally "log"): one day at a time, from every tab. It keeps
// nothing of its own: the day's To Do tasks (tick them off here), the Food, Gym
// and Journal boxes and the weight each belong to their tab, and use the same
// pieces as those tabs (ui/daylog.js), so typing here or there saves the same.
const logState = {
  day: null,          // 'YYYY-MM-DD'
  tasks: [],
  texts: {},          // the day's text per tab, e.g. texts.gym
  weight: null,
  workouts: [],       // templates, for the Gym box's +
  foodTemplates: [],  // for the Food box's +
};

// --- Data ---

async function logLoad() {
  await dayFlush();
  logState.day ??= today();
  let day;
  [day, logState.workouts, logState.foodTemplates] = await Promise.all([
    call("log_get_day", logState.day),
    call("templates_get", "Gym"),
    call("templates_get", "Food"),
  ]);
  logState.tasks = day.tasks;
  logState.texts = { gym: day.gym, food: day.food, journal: day.journal };
  logState.weight = day.weight;
  logRender();
}

function logGoToDay(day) {
  logState.day = day;
  logLoad();
}

// --- Drawing ---

function logRender() {
  const day = logState.day;
  $("log-daybar").replaceChildren(dayBar(day, logGoToDay));

  // Tasks: open ones first, then ones completed (today).
  const tasks = [...logState.tasks].sort((a, b) => a.completed - b.completed);
  $("log-tasks").replaceChildren(...tasks.map(logTaskRow));

  const texts = logState.texts;
  $("log-boxes").replaceChildren(
    dayBox({ kind: "food", label: "Food", day, text: texts.food, save: "food_save_day",
             templates: templateItems(logState.foodTemplates), addTitle: "Add a template" }),
    dayBox({ kind: "gym", label: "Gym", day, text: texts.gym, save: "gym_save_day",
             templates: templateItems(logState.workouts), addTitle: "Add a template" }),
    dayBox({ kind: "journal", label: "Journal", day, text: texts.journal, save: "journal_save_day" }),
    weightBox(day, logState.weight),
  );
}

function logTaskRow(task) {
  const check = el("button", {
    class: "check", title: task.completed ? "Mark as not completed" : "Mark as completed",
    onclick: () => call("todo_toggle_task", task.id).then(logLoad),
  }, ...(task.completed ? [el("span", { class: "check-mark" })] : []));
  const overdue = !task.completed && task.do_date < today();
  return el("li", { class: task.completed ? "task done" : "task" },
    check,
    el("div", { class: "task-body" },
      el("span", { class: "task-title" }, task.title),
      el("div", { class: "task-meta" }, task.list_name,
        ...(overdue ? [" · ", el("span", { class: "overdue" }, dateLabel(task.do_date, false))] : [])),
    ),
  );
}

// --- Events ---

// If the app is left open overnight, "today" moves on when you come back.
let logLastToday = today();
window.addEventListener("focus", () => {
  if (today() === logLastToday) return;
  if (logState.day === logLastToday) logState.day = today();
  logLastToday = today();
  logLoad();
});

// Leaving the tab saves pending edits; coming back refreshes (tasks may have changed).
document.addEventListener("tabshown", (e) => (e.detail === "log" ? logLoad() : dayFlush()));

logLoad();
