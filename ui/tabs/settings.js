// Settings tab: which data folder the app uses (your own, or test data to try
// changes to the app on: app/datafolder.py), and that folder's README.md
// (what's in it, every table by tab), shown as a page.
const FOLDER_LABELS = { personal: "Your data", test: "Test data" };

async function settingsLoad() {
  const [status, readme] = await Promise.all([call("settings_get_data_folder"), call("settings_get_readme")]);
  settingsRenderFolder(status);
  $("settings-readme").replaceChildren(...markdown(readme));
}

// Every tab shows the "Test data" badge while you're not on your own data.
function settingsShowBadge(status) {
  $("test-data-badge").hidden = status.which === "personal";
  $("test-data-badge").textContent = status.which === "test" ? "Test data" : "Test folder";
}

function settingsRenderFolder(status) {
  settingsShowBadge(status);
  const notes = [];
  if (status.error) notes.push(el("p", { class: "folder-note problem" }, status.error));
  if (status.fixed) {
    notes.push(el("p", { class: "folder-note muted" }, "LIFEOS_DATA_DIR sets the folder, so it can't be changed here:"),
               el("code", { class: "settings-path" }, status.path));
  }
  const choices = status.fixed ? [] : Object.entries(status.folders).map(([which, path]) => {
    const chosen = status.which === which;
    return el("div", { class: `folder-choice${chosen ? " chosen" : ""}` },
      el("label", {},
        el("input", { type: "radio", name: "data-folder", checked: chosen ? "" : null,
                      onchange: () => settingsUseFolder(which) }),
        FOLDER_LABELS[which]),
      el("code", { class: "settings-path" }, path),
      ...(which === "test" && chosen ? [el("button", { class: "text-button", onclick: settingsResetTest }, "Reset test data")] : []),
    );
  });
  $("settings-data-folder").replaceChildren(...notes, ...choices);
}

// Saves anything still being typed, switches, then reloads every tab on the new folder.
async function settingsSwitch(method, ...args) {
  await dayFlush();
  await templatesFlush();
  try {
    await call(method, ...args);
  } catch (err) {
    showToast(err.message || String(err));
    settingsLoad();
    return;
  }
  location.reload();
}

const settingsUseFolder = (which) => settingsSwitch("settings_use_data_folder", which);
const settingsResetTest = () => settingsSwitch("settings_reset_test_data");

// The bits of Markdown the README uses: # headings, paragraphs, - lists,
// | tables |, and `code`. Built as elements, so the text is never run as HTML.
function markdown(text) {
  const inline = (s) => s.split(/(`[^`]*`)/).map((part) =>
    part.startsWith("`") && part.endsWith("`") && part.length > 1 ? el("code", {}, part.slice(1, -1)) : part);
  const cells = (line) => line.trim().slice(1, -1).split(/(?<!\\)\|/).map((c) => c.trim().replaceAll("\\|", "|"));
  const blocks = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    const heading = line.match(/^(#{1,4}) (.*)$/);
    if (heading) {
      blocks.push(el(`h${heading[1].length}`, {}, ...inline(heading[2])));
    } else if (line.startsWith("- ")) {
      const items = [];
      for (; i < lines.length && lines[i].startsWith("- "); i++) items.push(el("li", {}, ...inline(lines[i].slice(2))));
      i--;
      blocks.push(el("ul", {}, ...items));
    } else if (line.startsWith("|")) {
      const rows = [];
      for (; i < lines.length && lines[i].startsWith("|"); i++) rows.push(cells(lines[i]));
      i--;
      const [head, , ...body] = rows;  // the second row is the |---| line
      blocks.push(el("div", { class: "table-scroll" }, el("table", { class: "data-table compact" },
        el("thead", {}, el("tr", {}, ...head.map((c) => el("th", {}, ...inline(c))))),
        el("tbody", {}, ...body.map((r) => el("tr", {}, ...r.map((c) => el("td", {}, ...inline(c)))))),
      )));
    } else {
      const para = [];
      for (; i < lines.length && lines[i].trim() && !/^(#|- |\|)/.test(lines[i]); i++) para.push(lines[i]);
      i--;
      blocks.push(el("p", {}, ...inline(para.join(" "))));
    }
  }
  return blocks;
}

document.addEventListener("tabshown", (e) => { if (e.detail === "settings") settingsLoad(); });
call("settings_get_data_folder").then(settingsShowBadge);
