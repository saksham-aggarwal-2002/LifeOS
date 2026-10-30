// Food tab. Three views (sidebar):
//   "diary"    Food Diary: Food owns its daily log, so it starts with the Food
//              box for one day (the same box as in the Overview), then every
//              day's text beside the foods eaten, each with its own numbers
//   "foods"    Foods: the library, macros per an amount of a unit, edited in place
//   "templates" recipes etc. (text files) for the Food box's +: ui/templates.js
const food = {
  view: "diary",
  day: today(),         // the day in the Food box
  diary: [],            // [{ id, day, body, status, items: [{ name, amount, unit, calories.. }], total }]
  foods: [],
  editing: null,        // food entry id whose items are being edited
  draft: [],            // its rows while editing: { name, amount, unit, calories, protein, carbs, fat }
};

const MACROS = ["calories", "protein", "carbs", "fat"];
const MACRO_LABELS = { calories: "kcal", protein: "Protein", carbs: "Carbs", fat: "Fat" };

// --- Data ---

async function foodLoad() {
  [food.foods, , food.diary] = await Promise.all([
    call("food_get_foods"),
    templatesLoad("Food"),
    food.view === "diary" ? call("food_get_diary") : [],
  ]);
  foodRender();
}

async function foodSelect(view) {
  food.view = view;
  food.editing = null;
  foodLoad().then(() => { if (view === "diary") foodLoadDay(); });  // templates may have changed
}

// The Food box: the day's text, saved by food_save_day like the Overview's.
async function foodLoadDay() {
  await dayFlush();
  const text = await call("food_get_day", food.day);
  $("food-daylog").replaceChildren(
    dayBar(food.day, (day) => { food.day = day; foodLoadDay(); }, { small: true }),
    dayBox({ kind: "food", label: "Food", day: food.day, text, save: "food_save_day",
             templates: templateItems(templatesState.Food.list), addTitle: "Add a template",
             onSaved: () => { if (food.view === "diary") foodLoad(); } }),
  );
}

// "Edit" on a past day: open it in the Food box at the top.
function foodEditDay(day) {
  food.day = day;
  foodLoadDay();
  $("food-daylog").scrollIntoView({ behavior: "smooth" });
}

const findFood = (name) => food.foods.find((f) => f.name.trim().toLowerCase() === name.trim().toLowerCase());

// --- Formatting ---

const fmtMacro = (n, m) => fmtNumber(n, m === "calories" ? 0 : 1);
const macroCells = (x) => MACROS.map((m) => el("td", { class: "num" }, x ? fmtMacro(x[m], m) : ""));
const macroHeads = () => MACROS.map((m) => el("th", { class: "num" }, MACRO_LABELS[m]));

// --- Drawing ---

function foodRender() {
  document.querySelectorAll("#tab-food .sidebar .nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === food.view);
  });
  $("food-diary").hidden = food.view !== "diary";
  $("food-daylog").hidden = food.view !== "diary";
  $("food-foods").hidden = food.view !== "foods";
  $("food-templates").hidden = food.view !== "templates";
  $("food-subtitle").textContent = "";

  showExtractButton($("food-extract"), food.view === "diary", food.diary);
  if (food.view === "diary") {
    $("food-title").textContent = "Food Diary";
    const days = food.diary.length;
    $("food-subtitle").textContent = days ? `${days} day${days === 1 ? "" : "s"} logged` : "";
    foodRenderDiary();
  } else if (food.view === "foods") {
    $("food-title").textContent = "Foods";
    foodRenderFoods();
  } else {
    $("food-title").textContent = "Templates";
    templatesRender("Food", $("food-templates"), { newLabel: "+ New template", placeholder: "- Oats 80 g\n- Milk 200 ml" });
  }
}

// --- Diary view ---

function foodRenderDiary() {
  $("food-diary").replaceChildren(...food.diary.map((entry) => {
    const editing = food.editing === entry.id;
    return diaryDay({
      day: entry.day, status: entry.status, body: entry.body, editing,
      data: editing ? el("div", { class: "item-editor", id: "food-item-editor" }) : foodItemsTable(entry),
      onEditNote: () => foodEditDay(entry.day),
      onEditData: () => foodStartEditing(entry),
    });
  }));
  if (food.editing) foodRenderEditor();
}

// A day's items in full: the same columns as Edit data, then the day's total.
function foodItemsTable(entry) {
  if (!entry.items.length) return el("p", { class: "muted diary-empty" }, "No foods yet");
  return el("div", { class: "table-scroll" }, el("table", { class: "data-table compact food-items" },
    el("thead", {}, el("tr", {},
      el("th", {}, "Food"), el("th", { class: "num" }, "Amount"), el("th", {}, "Unit"), ...macroHeads())),
    el("tbody", {}, ...entry.items.map((item) => el("tr", {},
      el("td", { class: "item-name" }, item.name),
      el("td", { class: "num" }, item.amount == null ? "" : fmtNumber(item.amount, 2)),
      el("td", { class: "muted" }, item.unit),
      ...macroCells(item),
    ))),
    ...(entry.items.length > 1 ? [el("tfoot", {}, el("tr", {},
      el("td", {}, "Total"), el("td", {}), el("td", {}), ...macroCells(entry.total)))] : []),
  ));
}

// --- Editing a day's items by hand ---

const FOOD_ITEM_FIELDS = ["name", "amount", "unit", ...MACROS];
const foodBlankRow = () => Object.fromEntries(FOOD_ITEM_FIELDS.map((f) => [f, ""]));
const foodIsBlank = (row) => FOOD_ITEM_FIELDS.every((f) => String(row[f]).trim() === "");

function foodStartEditing(entry) {
  food.editing = entry.id;
  food.draft = entry.items.map((item) => Object.fromEntries(FOOD_ITEM_FIELDS.map((f) => [f, item[f] ?? ""])));
  if (!food.draft.length) food.draft.push(foodBlankRow());
  foodRenderDiary();
  document.querySelector("#food-item-editor input")?.focus();
}

// A row naming a food in the library, with an amount, gets that food's unit
// and numbers for the amount (the same sum as food.for_amount in Python).
// They stay editable, and are saved as they are.
function foodFillFromLibrary(row) {
  const f = findFood(row.name);
  const amount = Number(row.amount);
  if (!f || row.amount === "" || !(amount >= 0)) return false;
  row.unit = f.unit;
  for (const m of MACROS) row[m] = Math.round((f[m] * amount / f.per_amount) * 10) / 10;
  return true;
}

function foodRenderEditor() {
  const box = $("food-item-editor");
  if (!box) return;
  keepingFocus(() => box.replaceChildren(...foodEditorContent()));
}

function foodEditorContent() {
  const input = (row, field, i, attrs = {}) => {
    const node = el("input", {
      class: `set-input ${field}`, "data-key": `${field}-${i}`, ...attrs,
      oninput: (e) => {
        row[field] = e.target.value;
        if ((field === "name" || field === "amount") && foodFillFromLibrary(row)) foodRenderEditor();
      },
    });
    node.value = row[field] ?? "";
    return node;
  };
  const number = { type: "number", min: "0", step: "any" };
  const addRow = () => {
    food.draft.push(foodBlankRow());
    foodRenderEditor();
    document.querySelector(`[data-key="name-${food.draft.length - 1}"]`)?.focus();
  };

  return [
    el("datalist", { id: "food-library-names" }, ...food.foods.map((f) => el("option", { value: f.name }))),
    el("div", { class: "table-scroll" }, el("table", {
      class: "data-table compact edit-table item-table",
      onkeydown: (e) => {
        if (e.key === "Escape") foodStopEditing();
        else if (e.key === "Enter" && e.metaKey) foodSaveDraft();
        else if (e.key === "Enter" && e.target.tagName === "INPUT") addRow();
      },
    },
      el("thead", {}, el("tr", {},
        el("th", {}, "Food"), el("th", {}, "Amount"), el("th", {}, "Unit"), ...macroHeads(), el("th", {}),
      )),
      el("tbody", {}, ...food.draft.map((row, i) => el("tr", {},
        el("td", {}, input(row, "name", i, { list: "food-library-names" })),
        el("td", {}, input(row, "amount", i, number)),
        el("td", {}, input(row, "unit", i)),
        ...MACROS.map((m) => el("td", { class: "num" }, input(row, m, i, number))),
        el("td", {}, el("button", {
          class: "icon-button", title: "Remove",
          onclick: () => { food.draft.splice(i, 1); foodRenderEditor(); },
        }, icon("trash"))),
      ))),
    )),
    el("div", { class: "set-editor-actions" },
      el("button", { class: "text-button", onclick: addRow }, "+ Add food"),
      el("span", { class: "spacer" }),
      el("button", { class: "text-button", onclick: foodStopEditing }, "Cancel"),
      el("button", { class: "primary-button", onclick: foodSaveDraft }, "Save"),
    ),
  ];
}

function foodStopEditing() {
  food.editing = null;
  food.draft = [];
  foodRenderDiary();
}

async function foodSaveDraft() {
  try {
    await call("food_save_items", food.editing, food.draft.filter((row) => !foodIsBlank(row)));
  } catch (err) {
    showToast(err.message || String(err));
    return;
  }
  food.editing = null;
  food.draft = [];
  foodLoad();
}

// --- Foods view: the library, edited in place ---

const FOOD_COLUMNS = [
  ["name", "Name", "text"], ["per_amount", "Per", "number"], ["unit", "Unit", "text"],
  ["calories", "kcal", "number"], ["protein", "Protein", "number"], ["carbs", "Carbs", "number"], ["fat", "Fat", "number"],
];

function foodRenderFoods() {
  $("food-subtitle").textContent = food.foods.length ? `${food.foods.length} saved` : "";
  if (!food.foods.length) return $("food-food-table").replaceChildren();
  $("food-food-table").replaceChildren(el("div", { class: "table-scroll" }, el("table", { class: "data-table compact edit-table food-table" },
    el("thead", {}, el("tr", {},
      ...FOOD_COLUMNS.map(([, label, type]) => el("th", { class: type === "number" && label !== "Per" ? "num" : "" }, label)),
      el("th", {}),
    )),
    el("tbody", {}, ...food.foods.map((f) => el("tr", {},
      ...FOOD_COLUMNS.map(([field, , type]) => {
        const input = el("input", {
          class: `set-input food-${field}`, "data-key": `food-${f.id}-${field}`,
          ...(type === "number" ? { type: "number", min: "0", step: "any" } : { maxlength: "100" }),
          // Save when you leave the box (or press Enter); Python checks the value.
          onchange: async (e) => {
            try {
              await call("food_update_food", f.id, { [field]: e.target.value });
              f[field] = type === "number" ? Number(e.target.value) : e.target.value.trim();
            } catch (err) {
              e.target.value = f[field];
              showToast(err.message || String(err));
            }
          },
          onkeydown: (e) => { if (e.key === "Enter") e.target.blur(); },
        });
        input.value = f[field];
        return el("td", {}, input);
      }),
      // Past days keep their numbers, so deleting a food is always allowed.
      el("td", {}, deleteButton(async () => { await call("food_delete_food", f.id); foodLoad(); })),
    ))),
  )));
}

$("food-new-food").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.querySelector("input");
  if (!input.value.trim()) return;
  try {
    const id = await call("food_create_food", input.value);
    input.value = "";
    await foodLoad();
    document.querySelector(`[data-key="food-${id}-calories"]`)?.focus();
  } catch (err) {
    showToast(err.message || String(err));
  }
});

// --- Events ---

document.querySelectorAll("#tab-food .sidebar > .nav-item").forEach((item) => {
  item.addEventListener("click", () => foodSelect(item.dataset.view));
});

$("food-extract").addEventListener("click", () =>
  extractPending($("food-extract"), food.diary, "extract_food", "days", foodLoad));

document.addEventListener("tabshown", (e) => (e.detail === "food" ? foodLoad().then(foodLoadDay) : templatesFlush()));
