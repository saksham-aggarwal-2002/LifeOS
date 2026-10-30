// To Do tab. `view` is what the main pane shows: "myday", "calendar",
// or a list id (number).
const todo = {
  view: "myday",
  lists: [],
  tasks: [],        // tasks shown in the main pane
  myDayCount: 0,    // open My Day tasks, for the sidebar
  showCompleted: true,
  calWeek: null,    // Monday of the week the calendar shows, 'YYYY-MM-DD'
  calTasks: [],     // tasks with a do date in that week
  unscheduled: [],  // open tasks with no do date
};

const TODO_TITLES = { myday: "My Day", calendar: "Calendar", deleted: "Recently deleted" };

// --- Data: ask Python, then redraw ---

async function todoLoad() {
  const [lists, myDay] = await Promise.all([call("todo_get_lists"), call("todo_get_my_day")]);
  todo.lists = lists;
  todo.myDayCount = myDay.filter((t) => !t.completed).length;
  if (todo.view === "myday") todo.tasks = myDay;
  else if (todo.view === "deleted") todo.tasks = await call("todo_get_deleted");
  else if (todoCurrentList()) todo.tasks = await call("todo_get_tasks", todo.view);
  else todo.tasks = [];
  if (todo.view === "calendar") {
    todo.calWeek ??= mondayOf(today());
    [todo.calTasks, todo.unscheduled] = await Promise.all([
      call("todo_get_calendar", todo.calWeek, addDays(todo.calWeek, 6)),
      call("todo_get_unscheduled"),
    ]);
  }
  todoRender();
}

function todoCurrentList() {
  return todo.lists.find((l) => l.id === todo.view);
}

function todoSelect(view) {
  todo.view = view;
  todoLoad();
}


// --- Drawing ---

function todoRender() {
  const list = todoCurrentList();
  const isMyDay = todo.view === "myday";

  // Sidebar.
  $("todo-lists").replaceChildren(...todo.lists.map(todoListItem));
  document.querySelector('#tab-todo [data-view="myday"] .count').textContent = todo.myDayCount || "";
  document.querySelectorAll("#tab-todo .nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === String(todo.view));
  });

  // Header.
  $("todo-title").textContent = list ? list.name : TODO_TITLES[todo.view];
  $("todo-subtitle").textContent = isMyDay
    ? new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })
    : "";
  $("todo-delete-list").hidden = !list || todo.lists.length <= 1;
  todoResetDeleteButton();

  // Tasks.
  $("todo-add-task").hidden = !(list || isMyDay);
  const isDeleted = todo.view === "deleted";
  const open = isDeleted ? todo.tasks : todo.tasks.filter((t) => !t.completed);
  const done = isDeleted ? [] : todo.tasks.filter((t) => t.completed);
  $("todo-tasks").replaceChildren(...open.map(isDeleted ? todoDeletedRow : todoTaskRow));
  $("todo-completed-toggle").hidden = done.length === 0;
  $("todo-completed-toggle").textContent = `${todo.showCompleted ? "▾" : "▸"} Completed  ${done.length}`;
  $("todo-completed").hidden = !todo.showCompleted;
  $("todo-completed").replaceChildren(...done.map(todoTaskRow));

  // Calendar.
  const isCalendar = todo.view === "calendar";
  $("cal-nav").hidden = !isCalendar;
  $("calendar").hidden = !isCalendar;
  if (isCalendar) {
    $("todo-subtitle").textContent = weekLabel(todo.calWeek);
    calRender();
  }
}

// --- Calendar: one week, Monday to Sunday. Drag a task to another day to change its
// do date, onto a day from the Unscheduled panel to give it one, or back to clear it. ---

function calWeekDays(monday) {
  return [0, 1, 2, 3, 4, 5, 6].map((n) => addDays(monday, n));
}

function calRender() {
  const byDay = {};
  for (const task of todo.calTasks) (byDay[task.do_date] ??= []).push(task);

  const columns = calWeekDays(todo.calWeek).map((day) => {
    const [y, m, d] = day.split("-").map(Number);
    const weekday = new Date(y, m - 1, d).toLocaleDateString("en-GB", { weekday: "short" });
    const column = el("div", { class: day === today() ? "cal-day today" : "cal-day", "data-day": day },
      el("div", { class: "cal-head" }, el("span", { class: "cal-weekday" }, weekday), el("span", { class: "cal-date" }, String(d))),
      ...(byDay[day] || []).map(calTask),
    );
    calDropZone(column, day);
    return column;
  });
  $("cal-week").replaceChildren(...columns);

  // Unscheduled panel: tasks grouped under their list's name.
  const panel = $("cal-unscheduled");
  panel.replaceChildren(el("div", { class: "cal-panel-title" }, "Unscheduled"));
  let lastList = null;
  for (const task of todo.unscheduled) {
    if (task.list_name !== lastList) {
      panel.append(el("div", { class: "cal-panel-list" }, task.list_name));
      lastList = task.list_name;
    }
    panel.append(calTask(task));
  }
  calDropZone(panel, null);
}

// Dropping a task on `element` sets its do date to `day` (null = clear it).
function calDropZone(element, day) {
  element.addEventListener("dragover", (e) => { e.preventDefault(); element.classList.add("drop-target"); });
  element.addEventListener("dragleave", (e) => {
    if (!element.contains(e.relatedTarget)) element.classList.remove("drop-target");
  });
  element.addEventListener("drop", async (e) => {
    e.preventDefault();
    element.classList.remove("drop-target");
    const taskId = Number(e.dataTransfer.getData("text/plain"));
    const task = [...todo.calTasks, ...todo.unscheduled].find((t) => t.id === taskId);
    if (!task || task.do_date === day) return;
    await call("todo_set_do_date", taskId, day);
    todoLoad();
  });
}

function calTask(task) {
  const item = el("div", {
    class: task.completed ? "cal-task done" : "cal-task",
    title: task.list_name,
  }, task.title);
  if (!task.completed) {
    item.draggable = true;
    item.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", String(task.id));
      e.dataTransfer.effectAllowed = "move";
    });
  }
  return item;
}

function calShiftWeek(n) {
  todo.calWeek = addDays(todo.calWeek, 7 * n);
  todoLoad();
}

// --- Sidebar lists: click to open, drag up or down to reorder ---

let todoDraggedList = null;  // id of the list being dragged

function todoListItem(list) {
  // A <div>, not a <button>: buttons can't always be dragged.
  const item = el("div", { class: "nav-item", role: "button", "data-view": list.id, draggable: "true", onclick: () => todoSelect(list.id) },
    el("span", {}, list.name),
    el("span", { class: "count" }, list.open_count || ""),
  );

  item.addEventListener("dragstart", (e) => {
    todoDraggedList = list.id;
    e.dataTransfer.setData("application/x-lifeos-list", String(list.id));
    e.dataTransfer.effectAllowed = "move";
    item.classList.add("dragging");
  });
  item.addEventListener("dragend", () => {
    todoDraggedList = null;
    document.querySelectorAll("#todo-lists .nav-item").forEach((i) => i.classList.remove("dragging", "drop-before", "drop-after"));
  });

  // While another list is dragged over this one, show a line above or below
  // depending on which half of the item the cursor is in.
  const dropAfter = (e) => e.offsetY > item.offsetHeight / 2;
  item.addEventListener("dragover", (e) => {
    if (todoDraggedList === null || todoDraggedList === list.id) return;
    e.preventDefault();
    item.classList.toggle("drop-before", !dropAfter(e));
    item.classList.toggle("drop-after", dropAfter(e));
  });
  item.addEventListener("dragleave", () => item.classList.remove("drop-before", "drop-after"));
  item.addEventListener("drop", async (e) => {
    e.preventDefault();
    const moved = todoDraggedList;
    if (moved === null || moved === list.id) return;
    const ids = todo.lists.map((l) => l.id).filter((id) => id !== moved);
    ids.splice(ids.indexOf(list.id) + (dropAfter(e) ? 1 : 0), 0, moved);
    await call("todo_reorder_lists", ids);
    todoLoad();
  });
  return item;
}

function todoTaskRow(task) {
  const reload = () => todoLoad();
  const inMyDay = task.do_date && task.do_date <= today();

  const check = el("button", {
    class: "check", title: task.completed ? "Mark as not completed" : "Mark as completed",
    onclick: () => call("todo_toggle_task", task.id).then(reload),
  }, ...(task.completed ? [el("span", { class: "check-mark" })] : []));

  // Title, plus a small line underneath: list name (in My Day) and do date.
  const title = el("span", { class: "task-title" }, task.title);
  title.addEventListener("dblclick", () =>
    editInPlace(title, task.title, (value) => call("todo_rename_task", task.id, value).then(reload))
  );
  const meta = [];
  if (todo.view === "myday") meta.push(task.list_name);
  if (task.do_date) {
    const label = dateLabel(task.do_date, task.completed);
    meta.push(el("span", { class: label.startsWith("Overdue") ? "overdue" : "" }, label));
  }
  const body = el("div", { class: "task-body" }, title);
  if (meta.length) {
    const metaEl = el("div", { class: "task-meta" });
    meta.forEach((part, i) => metaEl.append(...(i ? [" · ", part] : [part])));
    body.append(metaEl);
  }

  // Actions shown on hover: do date, My Day toggle, delete.
  const dateButton = el("button", {
    class: task.do_date ? "icon-button opens-popover on" : "icon-button opens-popover",
    title: "Set do date",
  }, icon("calendar"));
  dateButton.addEventListener("click", () =>
    openDatePicker(dateButton, task.do_date, (iso) => call("todo_set_do_date", task.id, iso).then(reload))
  );
  const sun = el("button", {
    class: inMyDay ? "icon-button on" : "icon-button",
    title: inMyDay ? "Remove from My Day" : "Add to My Day",
    onclick: () => call("todo_set_do_date", task.id, inMyDay ? null : today()).then(reload),
  }, icon("sun"));
  const remove = el("button", {
    class: "icon-button", title: "Delete task",
    onclick: async () => {
      await call("todo_delete_task", task.id);
      reload();
      showToast(`Deleted “${task.title}”`, "Undo", () => call("todo_restore_task", task.id).then(reload));
    },
  }, icon("trash"));

  return el("li", { class: task.completed ? "task done" : "task" },
    check, body, el("div", { class: "task-actions" }, dateButton, sun, remove));
}

// A row in Recently deleted: title, where it came from, and Restore.
function todoDeletedRow(task) {
  const when = parseDate(task.deleted_at.slice(0, 10)).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return el("li", { class: "task deleted" },
    el("div", { class: "task-body" },
      el("span", { class: "task-title" }, task.title),
      el("div", { class: "task-meta" }, `${task.list_name} · deleted ${when}`),
    ),
    el("button", {
      class: "restore-button",
      onclick: async () => {
        await call("todo_restore_task", task.id);
        todoLoad();
        showToast(`Restored “${task.title}” to ${task.list_name}`);
      },
    }, icon("restore"), "Restore"),
  );
}

// Swap an element for a text input; Enter or clicking away saves, Escape cancels.
function editInPlace(element, value, onSave) {
  const input = el("input", { class: "edit-input", value });
  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    const text = input.value.trim();
    if (save && text && text !== value) onSave(text);
    else input.replaceWith(element);
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") finish(true);
    if (e.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => finish(true));
  element.replaceWith(input);
  input.focus();
  input.select();
}

// --- Events ---

document.querySelectorAll("#tab-todo .sidebar > .nav-item").forEach((item) => {
  item.addEventListener("click", () => todoSelect(item.dataset.view));
});

$("todo-new-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.querySelector("input");
  const name = input.value.trim();
  if (!name) return;
  input.value = "";
  todoSelect(await call("todo_create_list", name));  // jump to the new list
});

// In My Day, new tasks go to your first list with today's do date.
$("todo-add-task").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.querySelector("input");
  const title = input.value.trim();
  if (!title) return;
  input.value = "";
  if (todo.view === "myday") await call("todo_add_task", null, title, today());
  else await call("todo_add_task", todo.view, title);
  todoLoad();
});

$("todo-completed-toggle").addEventListener("click", () => {
  todo.showCompleted = !todo.showCompleted;
  todoRender();
});

$("todo-title").addEventListener("dblclick", () => {
  const list = todoCurrentList();
  if (!list) return;
  editInPlace($("todo-title"), list.name, async (value) => {
    await call("todo_rename_list", list.id, value);
    todoLoad();
  });
});

// Deleting a list needs two clicks so it can't happen by accident.
$("todo-delete-list").addEventListener("click", async (e) => {
  const button = e.target;
  if (!button.dataset.armed) {
    button.dataset.armed = "1";
    button.textContent = "Click again to delete list and its tasks";
    button.classList.add("danger");
    return;
  }
  await call("todo_delete_list", todo.view);
  todoSelect("myday");
});

function todoResetDeleteButton() {
  const button = $("todo-delete-list");
  delete button.dataset.armed;
  button.textContent = "Delete list";
  button.classList.remove("danger");
}

$("cal-prev").addEventListener("click", () => calShiftWeek(-1));
$("cal-next").addEventListener("click", () => calShiftWeek(1));
$("cal-today").addEventListener("click", () => { todo.calWeek = null; todoLoad(); });

// When the window comes back into focus on a new day, My Day should update.
let todoLastDay = today();
window.addEventListener("focus", () => {
  if (today() !== todoLastDay) {
    todoLastDay = today();
    todoLoad();
  }
});

document.addEventListener("tabshown", (e) => { if (e.detail === "todo") todoLoad(); });

todoLoad();
