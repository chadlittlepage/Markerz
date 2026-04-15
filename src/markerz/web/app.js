/* Markerz v2 - pywebview UI */
"use strict";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let markers = [];           // Full marker list from Python
let filteredMarkers = [];   // After search filter
let selectedFrames = new Set();
let lastClickedFrame = null;
let sortCol = "tc";
let sortAsc = true;
let playheadFrame = -1;
let settings = {};
let modalOpen = false;
let hiddenCols = new Set();  // Set of hidden column indices

const COLOR_HEX = {
  Blue: "#3B82F6", Cyan: "#06B6D4", Green: "#22C55E", Yellow: "#EAB308",
  Red: "#EF4444", Pink: "#EC4899", Purple: "#A855F7", Fuchsia: "#D946EF",
  Rose: "#F43F5E", Lavender: "#A78BFA", Sky: "#38BDF8", Mint: "#34D399",
  Lemon: "#FDE047", Sand: "#D4A574", Cocoa: "#8B6914", Cream: "#FEF3C7",
};

const COL_NAMES = ["Color Dot", "Timecode", "Name", "Notes", "Duration"];

// Debounce timer for playhead navigation
let navTimer = null;

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

async function init() {
  settings = await pywebview.api.get_settings();

  bindHeaderEvents();
  bindTableEvents();
  bindKeyboard();
  bindContextMenu();
  bindModalEvents();
  initColumnResize();
  initHeaderContextMenu();

  // Restore saved column widths
  const saved = settings.column_widths;
  if (saved) applyColumnWidths(saved);

  // Restore hidden columns from settings
  if (settings.hidden_columns) {
    hiddenCols = new Set(settings.hidden_columns);
  }
  applyColumnVisibility();

  await refreshMarkers();
  setStatus("Ready");
}

// Called by Python when DOM is ready
window.addEventListener("pywebviewready", () => {
  init().catch(e => console.error("Init failed:", e));
});

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

async function refreshMarkers() {
  markers = await pywebview.api.get_markers();
  applyFilter();
}

function applyFilter() {
  const q = document.getElementById("search").value.toLowerCase();
  if (!q) {
    filteredMarkers = [...markers];
  } else {
    filteredMarkers = markers.filter(m =>
      m.name.toLowerCase().includes(q) ||
      m.note.toLowerCase().includes(q) ||
      m.color.toLowerCase().includes(q) ||
      m.tc.includes(q)
    );
  }
  sortMarkers();
  renderTable();
  updateStatus();
}

function sortMarkers() {
  filteredMarkers.sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  });
}

function updateStatus() {
  const total = markers.length;
  const shown = filteredMarkers.length;
  const sel = selectedFrames.size;
  let msg = `${shown} markers`;
  if (shown !== total) msg += ` (of ${total})`;
  if (sel > 0) msg += ` | ${sel} selected`;
  setStatus(msg);
}

function setStatus(msg) {
  document.getElementById("status-bar").textContent = msg;
}

// ---------------------------------------------------------------------------
// Table rendering
// ---------------------------------------------------------------------------

function renderTable() {
  const tbody = document.getElementById("marker-body");
  const frag = document.createDocumentFragment();
  const colStyles = settings.col_styles || {};
  const padding = settings.row_padding || 2;

  for (const m of filteredMarkers) {
    const tr = document.createElement("tr");
    tr.dataset.frame = m.frame;
    if (selectedFrames.has(m.frame)) tr.classList.add("selected");
    if (m.frame === playheadFrame) tr.classList.add("playhead");

    // Color dot
    const tdDot = document.createElement("td");
    tdDot.className = "col-dot";
    tdDot.textContent = "\u25CF";
    tdDot.style.color = COLOR_HEX[m.color] || "#888";
    if (hiddenCols.has(0)) tdDot.style.display = "none";
    tr.appendChild(tdDot);

    // Timecode
    const tdTc = document.createElement("td");
    tdTc.className = "col-tc";
    tdTc.textContent = m.tc;
    applyColStyle(tdTc, colStyles, 1);
    if (hiddenCols.has(1)) tdTc.style.display = "none";
    tr.appendChild(tdTc);

    // Name
    const tdName = document.createElement("td");
    tdName.className = "col-name";
    tdName.textContent = m.name;
    applyColStyle(tdName, colStyles, 2);
    if (hiddenCols.has(2)) tdName.style.display = "none";
    tr.appendChild(tdName);

    // Notes
    const tdNote = document.createElement("td");
    tdNote.className = "col-notes";
    tdNote.textContent = m.note;
    tdNote.style.paddingTop = (4 + padding) + "px";
    tdNote.style.paddingBottom = (4 + padding) + "px";
    applyColStyle(tdNote, colStyles, 3);
    if (hiddenCols.has(3)) tdNote.style.display = "none";
    tr.appendChild(tdNote);

    // Duration
    const tdDur = document.createElement("td");
    tdDur.className = "col-dur";
    tdDur.textContent = m.duration_tc;
    applyColStyle(tdDur, colStyles, 4);
    if (hiddenCols.has(4)) tdDur.style.display = "none";
    tr.appendChild(tdDur);

    frag.appendChild(tr);
  }

  tbody.replaceChildren(frag);
  renderSortArrows();
}

function applyColStyle(td, colStyles, col) {
  const s = colStyles[String(col)];
  if (!s) return;
  if (s.size) td.style.fontSize = s.size + "px";
  if (s.color) td.style.color = s.color;
}

function renderSortArrows() {
  document.querySelectorAll("#marker-table th[data-col]").forEach(th => {
    const existing = th.querySelector(".sort-arrow");
    if (existing) existing.remove();
    if (th.dataset.col === sortCol) {
      const span = document.createElement("span");
      span.className = "sort-arrow";
      span.textContent = sortAsc ? "\u25B2" : "\u25BC";
      th.appendChild(span);
    }
  });
}

function getRowByFrame(frame) {
  return document.querySelector(`#marker-body tr[data-frame="${frame}"]`);
}

// ---------------------------------------------------------------------------
// Header events
// ---------------------------------------------------------------------------

function bindHeaderEvents() {
  document.getElementById("search").addEventListener("input", () => applyFilter());
  document.getElementById("btn-add").addEventListener("click", showAddDialog);
  document.getElementById("btn-import").addEventListener("click", showImportDialog);
  document.getElementById("btn-settings").addEventListener("click", showSettingsDialog);

  // Sort headers (left-click only)
  document.querySelectorAll("#marker-table th[data-col]").forEach(th => {
    th.addEventListener("click", e => {
      if (e.button !== 0) return;  // left-click only
      const col = th.dataset.col;
      if (sortCol === col) {
        sortAsc = !sortAsc;
      } else {
        sortCol = col;
        sortAsc = true;
      }
      sortMarkers();
      renderTable();
    });
  });
}

// ---------------------------------------------------------------------------
// Table interaction
// ---------------------------------------------------------------------------

function bindTableEvents() {
  const tbody = document.getElementById("marker-body");
  const container = document.getElementById("table-container");

  tbody.addEventListener("click", e => {
    const tr = e.target.closest("tr");
    if (!tr) return;
    const frame = parseInt(tr.dataset.frame);

    if (e.metaKey || e.ctrlKey) {
      // Toggle selection
      if (selectedFrames.has(frame)) {
        selectedFrames.delete(frame);
        tr.classList.remove("selected");
      } else {
        selectedFrames.add(frame);
        tr.classList.add("selected");
      }
    } else if (e.shiftKey && lastClickedFrame !== null) {
      // Range select
      const allFrames = filteredMarkers.map(m => m.frame);
      const startIdx = allFrames.indexOf(lastClickedFrame);
      const endIdx = allFrames.indexOf(frame);
      if (startIdx >= 0 && endIdx >= 0) {
        const lo = Math.min(startIdx, endIdx);
        const hi = Math.max(startIdx, endIdx);
        selectedFrames.clear();
        for (let i = lo; i <= hi; i++) selectedFrames.add(allFrames[i]);
        refreshSelection();
      }
    } else {
      selectedFrames.clear();
      selectedFrames.add(frame);
      refreshSelection();
    }
    lastClickedFrame = frame;
    updateStatus();

    // Navigate playhead
    navigateToFrame(frame);
  });

  tbody.addEventListener("dblclick", e => {
    const tr = e.target.closest("tr");
    if (!tr) return;
    const frame = parseInt(tr.dataset.frame);
    showEditDialog(frame);
  });
}

function refreshSelection() {
  document.querySelectorAll("#marker-body tr").forEach(tr => {
    const f = parseInt(tr.dataset.frame);
    tr.classList.toggle("selected", selectedFrames.has(f));
  });
}

function navigateToFrame(frame) {
  clearTimeout(navTimer);
  navTimer = setTimeout(async () => {
    const m = markers.find(m => m.frame === frame);
    if (m) await pywebview.api.set_playhead(m.tc);
  }, 5);
}

// ---------------------------------------------------------------------------
// Keyboard
// ---------------------------------------------------------------------------

function bindKeyboard() {
  const container = document.getElementById("table-container");

  container.addEventListener("keydown", e => {
    if (modalOpen) return;

    // Arrow navigation
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const allFrames = filteredMarkers.map(m => m.frame);
      if (!allFrames.length) return;

      let curIdx = -1;
      if (lastClickedFrame !== null) {
        curIdx = allFrames.indexOf(lastClickedFrame);
      }

      let nextIdx;
      if (e.key === "ArrowDown") {
        nextIdx = curIdx < allFrames.length - 1 ? curIdx + 1 : curIdx;
      } else {
        nextIdx = curIdx > 0 ? curIdx - 1 : 0;
      }

      const nextFrame = allFrames[nextIdx];
      selectedFrames.clear();
      selectedFrames.add(nextFrame);
      lastClickedFrame = nextFrame;
      refreshSelection();
      updateStatus();

      // Scroll into view
      const row = getRowByFrame(nextFrame);
      if (row) row.scrollIntoView({ block: "nearest" });

      navigateToFrame(nextFrame);
      return;
    }

    // Delete
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      deleteSelected();
      return;
    }

    // Cmd+A
    if ((e.metaKey || e.ctrlKey) && e.key === "a") {
      e.preventDefault();
      selectAll();
      return;
    }

    // Cmd+Z
    if ((e.metaKey || e.ctrlKey) && e.key === "z") {
      e.preventDefault();
      undo();
      return;
    }

    // Cmd+C
    if ((e.metaKey || e.ctrlKey) && e.key === "c") {
      e.preventDefault();
      copySelected();
      return;
    }
  });

  // Give table focus on click
  container.addEventListener("click", () => container.focus());
}

async function deleteSelected() {
  if (!selectedFrames.size) {
    setStatus("No marker selected");
    return;
  }
  const frames = Array.from(selectedFrames);
  const count = await pywebview.api.delete_markers(frames);
  selectedFrames.clear();
  lastClickedFrame = null;
  await refreshMarkers();
  setStatus(`Deleted ${count} markers`);
}

async function undo() {
  const msg = await pywebview.api.undo();
  selectedFrames.clear();
  lastClickedFrame = null;
  await refreshMarkers();
  setStatus(msg);
}

function selectAll() {
  filteredMarkers.forEach(m => selectedFrames.add(m.frame));
  refreshSelection();
  updateStatus();
}

async function copySelected() {
  if (!selectedFrames.size) return;
  const lines = ["Timecode\tName\tNote\tDuration\tColor"];
  for (const m of filteredMarkers) {
    if (selectedFrames.has(m.frame)) {
      lines.push(`${m.tc}\t${m.name}\t${m.note}\t${m.duration_tc}\t${m.color}`);
    }
  }
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    setStatus(`Copied ${selectedFrames.size} markers`);
  } catch {
    setStatus("Copy failed");
  }
}

// ---------------------------------------------------------------------------
// Context menu
// ---------------------------------------------------------------------------

function bindContextMenu() {
  const menu = document.getElementById("context-menu");
  const container = document.getElementById("table-container");

  container.addEventListener("contextmenu", e => {
    e.preventDefault();
    if (modalOpen) return;

    const tr = e.target.closest("tr");
    if (tr) {
      const frame = parseInt(tr.dataset.frame);
      if (!selectedFrames.has(frame)) {
        selectedFrames.clear();
        selectedFrames.add(frame);
        lastClickedFrame = frame;
        refreshSelection();
      }
    }

    // Show/hide items based on selection
    const hasSelection = selectedFrames.size > 0;
    menu.querySelector('[data-action="edit"]').style.display = hasSelection ? "" : "none";
    const delItem = menu.querySelector('[data-action="delete"]');
    delItem.style.display = hasSelection ? "" : "none";
    if (hasSelection && selectedFrames.size > 1) {
      delItem.textContent = `Delete Selected (${selectedFrames.size})`;
    } else {
      delItem.textContent = "Delete Marker";
    }
    menu.querySelector('[data-action="copy"]').style.display = hasSelection ? "" : "none";

    menu.style.left = e.clientX + "px";
    menu.style.top = e.clientY + "px";
    menu.style.display = "block";
    // Block the immediate mouseup/click from dismissing the menu
    menu.dataset.justOpened = "1";
    setTimeout(() => { menu.dataset.justOpened = ""; }, 300);
  });

  menu.addEventListener("mouseup", e => {
    if (menu.dataset.justOpened) return;
    e.stopPropagation();
    const item = e.target.closest(".ctx-item");
    if (!item) return;
    const action = item.dataset.action;
    menu.style.display = "none";
    if (!action) return;

    switch (action) {
      case "edit":
        if (lastClickedFrame !== null) showEditDialog(lastClickedFrame);
        break;
      case "delete":
        deleteSelected();
        break;
      case "copy":
        copySelected();
        break;
      case "select-all":
        selectAll();
        break;
      case "settings":
        showSettingsDialog();
        break;
    }
  });

  // Also handle regular clicks for trackpad/accessibility
  menu.addEventListener("click", e => {
    e.stopPropagation();
    const item = e.target.closest(".ctx-item");
    if (!item) return;
    const action = item.dataset.action;
    menu.style.display = "none";
    if (!action) return;

    switch (action) {
      case "edit":
        if (lastClickedFrame !== null) showEditDialog(lastClickedFrame);
        break;
      case "delete":
        deleteSelected();
        break;
      case "copy":
        copySelected();
        break;
      case "select-all":
        selectAll();
        break;
      case "settings":
        showSettingsDialog();
        break;
    }
  });

  // Dismiss menu on click/mousedown outside
  document.addEventListener("mousedown", e => {
    if (menu.style.display === "block" && !menu.contains(e.target)) {
      menu.style.display = "none";
    }
  });
}

// ---------------------------------------------------------------------------
// Marker add/edit dialog
// ---------------------------------------------------------------------------

let markerDlgResolve = null;
let markerDlgMode = "add";
let markerDlgOldFrame = null;
let selectedColor = "Blue";

function bindModalEvents() {
  // Marker dialog
  document.getElementById("marker-done").addEventListener("click", () => closeMarkerDlg("done"));
  document.getElementById("marker-cancel").addEventListener("click", () => closeMarkerDlg("cancel"));
  document.getElementById("marker-remove").addEventListener("click", () => closeMarkerDlg("remove"));

  // Build color swatches
  const container = document.getElementById("marker-colors");
  for (const [name, hex] of Object.entries(COLOR_HEX)) {
    const el = document.createElement("span");
    el.className = "swatch";
    el.style.backgroundColor = hex;
    el.title = name;
    el.dataset.color = name;
    el.addEventListener("click", () => {
      container.querySelectorAll(".swatch").forEach(s => s.classList.remove("active"));
      el.classList.add("active");
      selectedColor = name;
    });
    container.appendChild(el);
  }

  // Timecode input masking
  [document.getElementById("marker-tc"), document.getElementById("marker-dur"),
   document.getElementById("import-tc")].forEach(bindTcMask);

  // Import dialog
  document.getElementById("import-cancel").addEventListener("click", () => closeImportDlg(false));
  document.getElementById("import-do").addEventListener("click", () => closeImportDlg(true));

  // Settings dialog
  document.getElementById("settings-done").addEventListener("click", closeSettingsDlg);
  document.getElementById("settings-reset").addEventListener("click", resetSettings);
  document.getElementById("preset-save").addEventListener("click", savePreset);
  document.getElementById("preset-load").addEventListener("click", loadPreset);
  document.getElementById("preset-delete").addEventListener("click", deletePreset);
  document.getElementById("preset-import").addEventListener("click", importPreset);
  document.getElementById("preset-export").addEventListener("click", exportPreset);
}

function bindTcMask(input) {
  input.addEventListener("keydown", e => {
    // Allow: backspace, delete, tab, arrows, home, end, select all
    if ([8, 9, 35, 36, 37, 38, 39, 40, 46].includes(e.keyCode)) return;
    if ((e.metaKey || e.ctrlKey) && e.key === "a") return;
    // Block non-digit
    if (!/^\d$/.test(e.key)) { e.preventDefault(); return; }
  });
  input.addEventListener("input", () => {
    let raw = input.value.replace(/\D/g, "").slice(0, 8);
    let formatted = "";
    for (let i = 0; i < raw.length; i++) {
      if (i > 0 && i % 2 === 0) formatted += ":";
      formatted += raw[i];
    }
    input.value = formatted;
  });
}

function showAddDialog() {
  markerDlgMode = "add";
  markerDlgOldFrame = null;
  document.getElementById("marker-dlg-title").textContent = "Add Marker";
  document.getElementById("marker-remove").style.display = "none";

  // Get playhead TC from Python
  pywebview.api.get_playhead_tc().then(tc => {
    document.getElementById("marker-tc").value = tc || "00:00:00:00";
    document.getElementById("marker-dur").value = "00:00:00:01";
    document.getElementById("marker-name").value = "";
    document.getElementById("marker-notes").value = "";
    selectSwatchColor("Blue");
    openOverlay("overlay-marker");
    document.getElementById("marker-name").focus();
  });
}

function showEditDialog(frame) {
  const m = markers.find(m => m.frame === frame);
  if (!m) return;

  markerDlgMode = "edit";
  markerDlgOldFrame = frame;
  document.getElementById("marker-dlg-title").textContent = "Edit Marker";
  document.getElementById("marker-remove").style.display = "";

  document.getElementById("marker-tc").value = m.tc;
  document.getElementById("marker-dur").value = m.duration_tc;
  document.getElementById("marker-name").value = m.name;
  document.getElementById("marker-notes").value = m.note;
  selectSwatchColor(m.color);
  openOverlay("overlay-marker");
}

function selectSwatchColor(color) {
  selectedColor = color;
  document.querySelectorAll("#marker-colors .swatch").forEach(s => {
    s.classList.toggle("active", s.dataset.color === color);
  });
}

async function closeMarkerDlg(action) {
  closeOverlay("overlay-marker");

  if (action === "cancel") return;

  if (action === "remove" && markerDlgOldFrame !== null) {
    await pywebview.api.delete_markers([markerDlgOldFrame]);
    await refreshMarkers();
    setStatus("Marker removed");
    return;
  }

  // Done - add or edit
  const tc = document.getElementById("marker-tc").value;
  const dur = document.getElementById("marker-dur").value;
  const name = document.getElementById("marker-name").value;
  const note = document.getElementById("marker-notes").value;
  const color = selectedColor;

  let msg;
  if (markerDlgMode === "edit" && markerDlgOldFrame !== null) {
    msg = await pywebview.api.edit_marker(markerDlgOldFrame, tc, color, name, note, dur);
  } else {
    msg = await pywebview.api.add_marker(tc, color, name, note, dur);
  }

  await refreshMarkers();
  setStatus(msg);
}

// ---------------------------------------------------------------------------
// Import dialog
// ---------------------------------------------------------------------------

let importData = null;

async function showImportDialog() {
  const filepath = await pywebview.api.open_file_dialog(
    "Import Markers",
    "EDL files (*.edl)|*.edl|CSV files (*.csv)|*.csv|All files (*.*)|*.*"
  );
  if (!filepath) return;

  const preview = await pywebview.api.import_preview(filepath);
  if (preview.error) {
    setStatus("Import error: " + preview.error);
    return;
  }

  importData = preview;
  document.getElementById("import-info").textContent =
    `File: ${preview.filename}\n` +
    `Format: ${preview.format}\n` +
    `Markers: ${preview.count}\n` +
    `Frame Rate: ${preview.fps}\n` +
    `First: ${preview.first_tc}\n` +
    `Last: ${preview.last_tc}\n` +
    `Colors: ${preview.colors}`;
  document.getElementById("import-tc").value = preview.first_tc;
  openOverlay("overlay-import");
}

async function closeImportDlg(doImport) {
  closeOverlay("overlay-import");
  if (!doImport || !importData) return;

  const tcOffset = document.getElementById("import-tc").value;
  const msg = await pywebview.api.commit_import(importData.filepath, tcOffset);
  importData = null;
  await refreshMarkers();
  setStatus(msg);
}

// ---------------------------------------------------------------------------
// Settings dialog
// ---------------------------------------------------------------------------

async function showSettingsDialog() {
  settings = await pywebview.api.get_settings();
  const colStyles = settings.col_styles || {};
  const container = document.getElementById("settings-columns");
  container.innerHTML = "";

  for (let col = 0; col < 5; col++) {
    const s = colStyles[String(col)] || {};
    const size = s.size || 13;
    const color = s.color || "#cccccc";

    const row = document.createElement("div");
    row.className = "setting-row";
    row.innerHTML =
      `<span class="setting-label">${COL_NAMES[col]}</span>` +
      `<input type="range" min="8" max="36" value="${size}" data-col="${col}">` +
      `<span class="range-val" id="sz-${col}">${size}</span>` +
      `<input type="color" value="${color}" data-col="${col}">`;
    container.appendChild(row);

    // Live preview
    const slider = row.querySelector('input[type="range"]');
    const valSpan = row.querySelector(".range-val");
    slider.addEventListener("input", () => {
      valSpan.textContent = slider.value;
      previewColStyle(col, parseInt(slider.value), null);
    });

    const colorInput = row.querySelector('input[type="color"]');
    colorInput.addEventListener("input", () => {
      previewColStyle(col, null, colorInput.value);
    });
  }

  // Padding — clone to strip accumulated listeners
  const oldPad = document.getElementById("setting-padding");
  const newPad = oldPad.cloneNode(true);
  oldPad.replaceWith(newPad);
  newPad.value = settings.row_padding || 2;
  document.getElementById("padding-val").textContent = settings.row_padding || 2;
  newPad.addEventListener("input", e => {
    document.getElementById("padding-val").textContent = e.target.value;
    settings.row_padding = parseInt(e.target.value);
    renderTable();
  });

  // Highlight
  document.getElementById("setting-highlight").value = settings.highlight_color || "#4a556c";

  // Presets
  await refreshPresetList();

  openOverlay("overlay-settings");
}

function previewColStyle(col, size, color) {
  if (!settings.col_styles) settings.col_styles = {};
  if (!settings.col_styles[String(col)]) settings.col_styles[String(col)] = {};
  if (size !== null) settings.col_styles[String(col)].size = size;
  if (color !== null) settings.col_styles[String(col)].color = color;
  renderTable();
}

async function closeSettingsDlg() {
  // Gather values
  const colStyles = {};
  document.querySelectorAll("#settings-columns .setting-row").forEach(row => {
    const slider = row.querySelector('input[type="range"]');
    const colorInput = row.querySelector('input[type="color"]');
    const col = slider.dataset.col;
    colStyles[col] = {
      size: parseInt(slider.value),
      color: colorInput.value,
    };
  });

  settings.col_styles = colStyles;
  settings.row_padding = parseInt(document.getElementById("setting-padding").value);
  settings.highlight_color = document.getElementById("setting-highlight").value;

  // Update highlight CSS variable
  const hl = settings.highlight_color;
  document.documentElement.style.setProperty("--accent-alpha",
    hl + "b3"); // ~70% opacity

  await pywebview.api.save_settings(settings);
  closeOverlay("overlay-settings");
  renderTable();
}

async function resetSettings() {
  settings.col_styles = {};
  settings.row_padding = 2;
  settings.highlight_color = "#4a556c";
  settings.column_widths = null;
  settings.hidden_columns = [];
  hiddenCols.clear();
  document.documentElement.style.setProperty("--accent-alpha", "rgba(74, 85, 108, 0.7)");
  await pywebview.api.save_settings(settings);

  // Reset column widths and visibility
  applyColumnVisibility();
  const table = document.getElementById("marker-table");
  const container = document.getElementById("table-container");
  const ths = Array.from(table.querySelectorAll("th"));
  // Clear explicit widths so they go back to defaults
  ths.forEach(th => { th.style.width = ""; });
  table.style.width = "";
  // Re-lock to pixel widths after layout recalculates
  requestAnimationFrame(() => {
    table.style.width = container.clientWidth + "px";
    ths.forEach(th => { th.style.width = th.offsetWidth + "px"; });
    saveColumnWidths();
  });

  renderTable();
  // Refresh the dialog
  showSettingsDialog();
}

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

async function refreshPresetList() {
  const list = await pywebview.api.get_presets();
  const select = document.getElementById("preset-list");
  select.innerHTML = '<option value="">-- Select --</option>';
  for (const name of list) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  }
}

async function savePreset() {
  const name = document.getElementById("preset-name").value.trim();
  if (!name) return;
  // Capture current column widths and hidden columns before saving
  saveColumnWidths();
  settings.hidden_columns = Array.from(hiddenCols);
  await pywebview.api.save_preset(name, settings);
  document.getElementById("preset-name").value = "";
  await refreshPresetList();
  setStatus(`Preset "${name}" saved`);
}

async function loadPreset() {
  const name = document.getElementById("preset-list").value;
  if (!name) return;
  settings = await pywebview.api.load_preset(name);

  // Apply hidden columns
  hiddenCols = new Set(settings.hidden_columns || []);
  applyColumnVisibility();

  // Apply column widths
  if (settings.column_widths) {
    applyColumnWidths(settings.column_widths);
  }

  // Apply highlight color
  if (settings.highlight_color) {
    document.documentElement.style.setProperty("--accent-alpha", settings.highlight_color + "b3");
  }

  closeOverlay("overlay-settings");
  renderTable();
  setStatus(`Preset "${name}" loaded`);
}

async function deletePreset() {
  const name = document.getElementById("preset-list").value;
  if (!name) return;
  await pywebview.api.delete_preset(name);
  await refreshPresetList();
  setStatus(`Preset "${name}" deleted`);
}

async function importPreset() {
  const result = await pywebview.api.import_preset();
  if (result) {
    await refreshPresetList();
    setStatus(`Preset "${result}" imported`);
  }
}

async function exportPreset() {
  const name = document.getElementById("preset-list").value;
  if (!name) return;
  await pywebview.api.export_preset(name);
  setStatus(`Preset "${name}" exported`);
}

// ---------------------------------------------------------------------------
// Modal helpers
// ---------------------------------------------------------------------------

function openOverlay(id) {
  modalOpen = true;
  const overlay = document.getElementById(id);
  overlay.classList.add("active");
  // Prevent clicks inside the modal from closing it (one-time setup)
  const modal = overlay.querySelector(".modal");
  if (modal && !modal.dataset.stopPropBound) {
    modal.addEventListener("click", e => e.stopPropagation());
    modal.dataset.stopPropBound = "1";
  }
}

function closeOverlay(id) {
  modalOpen = false;
  document.getElementById(id).classList.remove("active");
  // Refocus table for keyboard navigation
  document.getElementById("table-container").focus();
}

// Close modals on Escape
document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay.active").forEach(ov => {
      ov.classList.remove("active");
      modalOpen = false;
    });
  }
});

// ---------------------------------------------------------------------------
// Python -> JS callbacks (called via evaluate_js)
// ---------------------------------------------------------------------------

function updatePlayhead(tc, frame) {
  if (modalOpen) return;
  playheadFrame = frame;

  // Update playhead indicator
  document.querySelectorAll("#marker-body tr.playhead").forEach(tr => tr.classList.remove("playhead"));
  const row = getRowByFrame(frame);
  if (row) {
    row.classList.add("playhead");
    // Auto-select if table doesn't have focus
    if (document.activeElement !== document.getElementById("table-container")) {
      selectedFrames.clear();
      selectedFrames.add(frame);
      lastClickedFrame = frame;
      refreshSelection();
      row.scrollIntoView({ block: "nearest" });
    }
  }
}

async function onMarkersChanged() {
  if (modalOpen) return;
  const prevSelected = new Set(selectedFrames);
  await refreshMarkers();
  // Restore selection if frames still exist
  for (const f of prevSelected) {
    if (markers.some(m => m.frame === f)) selectedFrames.add(f);
  }
  refreshSelection();
  updateStatus();
}

function onTimelineChanged(name) {
  document.title = `Markerz - ${name}`;
  onMarkersChanged();
}

// ---------------------------------------------------------------------------
// Column resize
// ---------------------------------------------------------------------------

function initColumnResize() {
  const table = document.getElementById("marker-table");
  const container = document.getElementById("table-container");
  const ths = Array.from(table.querySelectorAll("th"));
  const MIN_COL = 40;

  // Set initial table width to fill container, lock all columns to px
  function lockAllWidths() {
    table.style.width = container.clientWidth + "px";
    ths.forEach(th => { th.style.width = th.offsetWidth + "px"; });
  }
  lockAllWidths();

  // On window resize, adjust last visible column to fill/shrink
  window.addEventListener("resize", () => {
    const containerW = container.clientWidth;
    const currentTableW = ths.reduce((sum, th, i) => sum + (hiddenCols.has(i) ? 0 : th.offsetWidth), 0);
    const diff = containerW - currentTableW;
    if (diff === 0) return;
    // Find last visible column and adjust it
    for (let j = ths.length - 1; j >= 0; j--) {
      if (!hiddenCols.has(j)) {
        const newW = Math.max(MIN_COL, ths[j].offsetWidth + diff);
        ths[j].style.width = newW + "px";
        break;
      }
    }
    table.style.width = containerW + "px";
  });

  for (let i = 0; i < ths.length; i++) {
    const th = ths[i];
    const handle = document.createElement("div");
    handle.className = "col-resize";
    th.appendChild(handle);

    handle.addEventListener("mousedown", e => {
      e.preventDefault();
      e.stopPropagation();

      // Snapshot all widths
      ths.forEach(t => { t.style.width = t.offsetWidth + "px"; });

      const startX = e.clientX;
      const startW = th.offsetWidth;

      // Find next visible column
      let nextTh = null;
      for (let j = i + 1; j < ths.length; j++) {
        if (!hiddenCols.has(j)) { nextTh = ths[j]; break; }
      }
      const nextStartW = nextTh ? nextTh.offsetWidth : 0;

      const onMove = ev => {
        let delta = ev.clientX - startX;
        if (startW + delta < MIN_COL) delta = MIN_COL - startW;

        if (nextTh) {
          // Trade with neighbor
          if (nextStartW - delta < MIN_COL) delta = nextStartW - MIN_COL;
          th.style.width = (startW + delta) + "px";
          nextTh.style.width = (nextStartW - delta) + "px";
        } else {
          // Last visible column: resize it and the table
          th.style.width = (startW + delta) + "px";
          const total = ths.reduce((s, t, idx) => s + (hiddenCols.has(idx) ? 0 : t.offsetWidth), 0);
          table.style.width = total + "px";
        }
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        saveColumnWidths();
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }
}

function applyColumnWidths(widths) {
  const MIN_COL = 40;
  const ths = document.querySelectorAll("#marker-table th");
  ths.forEach((th, i) => {
    if (widths[i]) th.style.width = Math.max(MIN_COL, widths[i]) + "px";
  });
}

function saveColumnWidths() {
  const ths = document.querySelectorAll("#marker-table th");
  const widths = Array.from(ths).map(th => th.offsetWidth);
  settings.column_widths = widths;
  pywebview.api.save_settings(settings).catch(() => {});
}

// ---------------------------------------------------------------------------
// Column visibility
// ---------------------------------------------------------------------------

const COL_LABELS = ["", "Timecode", "Name", "Notes", "Duration"];
const COL_CLASSES = ["col-dot", "col-tc", "col-name", "col-notes", "col-dur"];

function applyColumnVisibility() {
  const ths = document.querySelectorAll("#marker-table th");
  ths.forEach((th, i) => {
    th.style.display = hiddenCols.has(i) ? "none" : "";
  });
  // Also apply to all body rows
  document.querySelectorAll("#marker-body tr").forEach(tr => {
    const tds = tr.querySelectorAll("td");
    tds.forEach((td, i) => {
      td.style.display = hiddenCols.has(i) ? "none" : "";
    });
  });
}

function initHeaderContextMenu() {
  const headerMenu = document.createElement("div");
  headerMenu.id = "header-context-menu";
  headerMenu.style.cssText = `
    position: fixed; background: #2b2b2b; border: 1px solid #3d3d3d;
    border-radius: 4px; padding: 4px 0; min-width: 160px; z-index: 100; display: none;
  `;
  document.body.appendChild(headerMenu);

  const thead = document.querySelector("#marker-table thead");
  thead.addEventListener("contextmenu", e => {
    e.preventDefault();
    e.stopPropagation();

    headerMenu.innerHTML = "";
    // Column 0 (dot) is always visible, start from 1
    for (let i = 1; i < COL_LABELS.length; i++) {
      const item = document.createElement("div");
      const visible = !hiddenCols.has(i);
      item.style.cssText = "padding: 6px 20px; cursor: pointer; font-size: 13px; color: #ccc;";
      item.textContent = (visible ? "\u2713 " : "    ") + COL_LABELS[i];
      item.addEventListener("mouseenter", () => { item.style.background = "#4a556c"; });
      item.addEventListener("mouseleave", () => { item.style.background = ""; });
      item.addEventListener("click", ev => {
        ev.stopPropagation();
        if (visible) {
          hiddenCols.add(i);
        } else {
          hiddenCols.delete(i);
        }
        settings.hidden_columns = Array.from(hiddenCols);
        pywebview.api.save_settings(settings).catch(() => {});
        applyColumnVisibility();
        headerMenu.style.display = "none";
      });
      headerMenu.appendChild(item);
    }

    headerMenu.style.left = e.clientX + "px";
    headerMenu.style.top = e.clientY + "px";
    headerMenu.style.display = "block";
  });

  document.addEventListener("mousedown", e => {
    if (headerMenu.style.display === "block" && !headerMenu.contains(e.target)) {
      headerMenu.style.display = "none";
    }
  });
}

