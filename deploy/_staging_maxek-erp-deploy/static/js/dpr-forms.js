(function () {
  var VOLUME_UNITS = { Cum: 1, cum: 1, m3: 1, M3: 1, CUM: 1 };
  var AREA_UNITS = { Sqm: 1, sqm: 1, m2: 1, M2: 1, SQM: 1, Sqft: 1 };
  var STEEL_UNITS = { Kg: 1, kg: 1, MT: 1, mt: 1, Ton: 1, ton: 1, Tonne: 1, tonne: 1 };

  var state = {
    boqItems: [],
    steelShapes: [],
    pendingShapeSelect: null,
  };

  function parseNum(v) {
    var n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  }

  function average(vals) {
    var nums = vals.filter(function (v) { return v > 0; });
    if (!nums.length) return 0;
    return nums.reduce(function (a, b) { return a + b; }, 0) / nums.length;
  }

  function unitType(unit) {
    if (VOLUME_UNITS[unit]) return "volume";
    if (AREA_UNITS[unit]) return "area";
    if (STEEL_UNITS[unit]) return "steel";
    return "simple";
  }

  function steelWeightKg(dia, lengthM, bars) {
    if (dia <= 0 || lengthM <= 0 || bars <= 0) return 0;
    return (dia * dia * lengthM * bars) / 162;
  }

  function getForm() {
    return document.querySelector("[data-dpr-form]");
  }

  function syncProjectHidden(form) {
    var idSel = form.querySelector("[data-dpr-project-id]");
    var hidden = form.querySelector("#dpr_project_id_hidden");
    if (hidden && idSel) hidden.value = idSel.value || "";
  }

  function syncProjectDropdowns(form, source) {
    var idSel = form.querySelector("[data-dpr-project-id]");
    var nameSel = form.querySelector("[data-dpr-project-name]");
    if (!idSel || !nameSel) return;
    if (source === "id") {
      nameSel.value = idSel.value;
    } else {
      idSel.value = nameSel.value;
    }
    syncProjectHidden(form);
    loadBoqItems(form, idSel.value);
  }

  function uniqueBoqNumbers(items) {
    var seen = {};
    var list = [];
    items.forEach(function (item) {
      var num = item.boq_number || "";
      if (num && !seen[num]) {
        seen[num] = true;
        list.push(num);
      }
    });
    return list;
  }

  function boqItemsForNumber(boqNumber) {
    return state.boqItems.filter(function (i) { return i.boq_number === boqNumber; });
  }

  function isBillClient(form) {
    var sel = form.querySelector("[data-dpr-bill-client]");
    return sel && sel.value === "yes";
  }

  function updateBillingMode(form) {
    var billYes = isBillClient(form);
    var resourcePanel = form.querySelector("[data-dpr-resource-panel]");
    var costingHidden = form.querySelector("#dpr_for_costing");
    var hintYes = form.querySelector("[data-dpr-hint-yes]");
    var hintNo = form.querySelector("[data-dpr-hint-no]");
    if (resourcePanel) resourcePanel.hidden = billYes;
    if (costingHidden) costingHidden.value = billYes ? "no" : "yes";
    if (hintYes) hintYes.hidden = !billYes;
    if (hintNo) hintNo.hidden = billYes;
    if (!billYes && resourcePanel && !form.querySelector("[data-dpr-manpower-row]")) {
      addManpowerRow(form);
    }
  }

  function fillBoqDropdowns(form) {
    var numSel = form.querySelector("[data-dpr-boq-number]");
    var descSel = form.querySelector("[data-dpr-boq-description]");
    if (!numSel || !descSel) return;

    var numbers = uniqueBoqNumbers(state.boqItems);
    var continueBoq = form.getAttribute("data-continue-boq") || "";

    numSel.innerHTML = '<option value="">Select BOQ Number</option>';
    numbers.forEach(function (num) {
      var opt = document.createElement("option");
      opt.value = num;
      opt.textContent = num;
      if (continueBoq && continueBoq === num) opt.selected = true;
      numSel.appendChild(opt);
    });

    var filterNum = numSel.value || continueBoq;
    fillDescriptionDropdown(form, filterNum);
    numSel.disabled = !state.boqItems.length;
    descSel.disabled = !state.boqItems.length;

    if (filterNum) {
      var matches = boqItemsForNumber(filterNum);
      if (matches.length === 1) selectBoqItem(form, matches[0].id);
    }
  }

  function fillDescriptionDropdown(form, boqNumber) {
    var descSel = form.querySelector("[data-dpr-boq-description]");
    if (!descSel) return;
    descSel.innerHTML = '<option value="">Select BOQ Description</option>';
    state.boqItems.forEach(function (item) {
      if (boqNumber && item.boq_number !== boqNumber) return;
      var opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = (item.line_no ? item.line_no + ". " : "") + (item.item_description || "—");
      opt.dataset.boqNumber = item.boq_number || "";
      opt.dataset.unit = item.unit || "";
      opt.dataset.description = item.item_description || "";
      descSel.appendChild(opt);
    });
  }

  function selectBoqItem(form, itemId) {
    var item = state.boqItems.find(function (i) { return String(i.id) === String(itemId); });
    if (!item) return;
    var numSel = form.querySelector("[data-dpr-boq-number]");
    var descSel = form.querySelector("[data-dpr-boq-description]");
    var numHidden = form.querySelector("#dpr_boq_number_hidden");
    var descHidden = form.querySelector("#dpr_boq_description_hidden");
    var unitDisplay = form.querySelector("[data-dpr-unit-display]");
    var unitHidden = form.querySelector("#dpr_unit_hidden");

    if (numSel) numSel.value = item.boq_number || "";
    if (descSel) descSel.value = String(item.id);
    if (numHidden) numHidden.value = item.boq_number || "";
    if (descHidden) descHidden.value = item.item_description || "";
    if (unitDisplay) unitDisplay.value = item.unit || "";
    if (unitHidden) unitHidden.value = item.unit || "";
    showMeasurementPanel(form, item.unit || "");
  }

  function showMeasurementPanel(form, unit) {
    var panel = form.querySelector("[data-dpr-measurement-panel]");
    var vol = form.querySelector("[data-dpr-volume-panel]");
    var area = form.querySelector("[data-dpr-area-panel]");
    var steel = form.querySelector("[data-dpr-steel-panel]");
    var simple = form.querySelector("[data-dpr-simple-panel]");
    var ut = unitType(unit);
    if (!panel) return;
    panel.hidden = !unit;
    if (vol) {
      vol.hidden = ut !== "volume";
      if (ut === "volume") resetDimensionPanel(vol, ut);
    }
    if (area) {
      area.hidden = ut !== "area";
      if (ut === "area") resetDimensionPanel(area, ut);
    }
    if (steel) {
      steel.hidden = ut !== "steel";
      if (ut === "steel" && !steel.querySelector("[data-dpr-steel-line]")) addSteelLine(form);
    }
    if (simple) simple.hidden = ut !== "simple";
    recalcQuantity(form);
  }

  function resetDimensionPanel(panel, ut) {
    panel.querySelectorAll("[data-dpr-readings]").forEach(function (c) { c.innerHTML = ""; });
    var dims = ut === "volume" ? ["length", "width", "depth"] : ["length", "width"];
    dims.forEach(function (dim) {
      var container = panel.querySelector('[data-dpr-readings="' + dim + '"]');
      if (!container) return;
      addReadingRow(container, dim);
      addReadingRow(container, dim);
    });
  }

  function addReadingRow(container, dim) {
    var row = document.createElement("div");
    row.className = "dpr-reading-row";
    row.innerHTML =
      '<input type="number" min="0" step="0.001" data-reading="' + dim + '" placeholder="Enter ' + dim + '">' +
      '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-remove-reading><i class="fa-solid fa-trash"></i></button>';
    row.querySelector("[data-remove-reading]").addEventListener("click", function () {
      if (container.children.length > 1) row.remove();
      recalcQuantity(getForm());
    });
    row.querySelector("input").addEventListener("input", function () { recalcQuantity(getForm()); });
    container.appendChild(row);
  }

  function activeMeasurementPanel(form) {
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);
    if (ut === "volume") return form.querySelector("[data-dpr-volume-panel]");
    if (ut === "area") return form.querySelector("[data-dpr-area-panel]");
    if (ut === "steel") return form.querySelector("[data-dpr-steel-panel]");
    if (ut === "simple") return form.querySelector("[data-dpr-simple-panel]");
    return null;
  }

  function collectReadings(form, dim) {
    var scope = activeMeasurementPanel(form) || form;
    var inputs = scope.querySelectorAll('[data-reading="' + dim + '"]');
    var vals = [];
    inputs.forEach(function (inp) { vals.push(parseNum(inp.value)); });
    return vals;
  }

  function recalcQuantity(form) {
    if (!form) return;
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);
    var qty = 0;
    var unitEl = form.querySelector("[data-dpr-calculated-unit]");
    if (unitEl) unitEl.textContent = unit;

    if (ut === "volume") {
      var al = average(collectReadings(form, "length"));
      var aw = average(collectReadings(form, "width"));
      var ad = average(collectReadings(form, "depth"));
      qty = al * aw * ad;
    } else if (ut === "area") {
      qty = average(collectReadings(form, "length")) * average(collectReadings(form, "width"));
    } else if (ut === "steel") {
      form.querySelectorAll("[data-dpr-steel-line]").forEach(function (line) {
        qty += parseNum(line.querySelector("[data-steel-qty]") && line.querySelector("[data-steel-qty]").textContent);
      });
    } else {
      var simple = form.querySelector("[data-dpr-simple-qty]");
      qty = simple ? parseNum(simple.value) : 0;
    }

    var el = form.querySelector("[data-dpr-calculated-qty]");
    if (el) el.textContent = qty.toFixed(4);
  }

  function recalcSteelLine(line, unit) {
    var dia = parseNum(line.querySelector("[data-steel-dia]") && line.querySelector("[data-steel-dia]").value);
    var bars = parseInt(line.querySelector("[data-steel-bars]") && line.querySelector("[data-steel-bars]").value, 10) || 0;
    var shapeSel = line.querySelector("[data-steel-shape]");
    var formula = "straight";
    var cuttingM = 0;
    if (shapeSel && shapeSel.selectedOptions[0]) {
      formula = shapeSel.selectedOptions[0].dataset.formula || "straight";
    }
    if (formula === "straight") {
      cuttingM = parseNum(line.querySelector("[data-steel-cutting]") && line.querySelector("[data-steel-cutting]").value);
    } else {
      var sides = [];
      line.querySelectorAll("[data-steel-side]").forEach(function (inp) {
        sides.push(parseNum(inp.value));
      });
      var sumMm = sides.filter(function (v) { return v > 0; }).reduce(function (a, b) { return a + b; }, 0);
      cuttingM = sumMm / 1000;
    }
    var kg = steelWeightKg(dia, cuttingM, bars);
    var lineQty = (unit === "MT" || unit === "mt") ? kg / 1000 : kg;
    var qtyEl = line.querySelector("[data-steel-qty]");
    if (qtyEl) qtyEl.textContent = lineQty.toFixed(4);
    recalcQuantity(getForm());
  }

  function addSteelLine(form) {
    var template = form.querySelector("[data-dpr-steel-line-template]");
    var container = form.querySelector("[data-dpr-steel-lines]");
    if (!template || !container) return;
    var line = template.content.cloneNode(true).querySelector("[data-dpr-steel-line]");
    bindSteelLine(form, line);
    container.appendChild(line);
    recalcSteelLine(line, (form.querySelector("#dpr_unit_hidden") || {}).value || "");
  }

  function bindSteelLine(form, line) {
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    line.querySelector("[data-dpr-remove-steel-line]").addEventListener("click", function () {
      line.remove();
      recalcQuantity(form);
    });
    ["data-steel-bars", "data-steel-dia", "data-steel-cutting"].forEach(function (sel) {
      var el = line.querySelector("[" + sel + "]");
      if (el) el.addEventListener("input", function () { recalcSteelLine(line, unit); });
      if (el) el.addEventListener("change", function () { recalcSteelLine(line, unit); });
    });
    var shapeSel = line.querySelector("[data-steel-shape]");
    if (shapeSel) {
      shapeSel.addEventListener("change", function () {
        if (shapeSel.value === "new") {
          state.pendingShapeSelect = shapeSel;
          openShapeModal();
          shapeSel.value = "";
          return;
        }
        var opt = shapeSel.selectedOptions[0];
        var formula = opt ? opt.dataset.formula : "straight";
        var sides = opt ? parseInt(opt.dataset.sides, 10) || 1 : 1;
        var cuttingWrap = line.querySelector("[data-steel-cutting-wrap]");
        var sidesWrap = line.querySelector("[data-steel-sides-wrap]");
        if (cuttingWrap) cuttingWrap.hidden = formula !== "straight";
        if (sidesWrap) {
          sidesWrap.hidden = formula === "straight";
          if (formula !== "straight") buildSteelSides(line, sides);
        }
        recalcSteelLine(line, unit);
      });
    }
    var addSideBtn = line.querySelector("[data-steel-add-side]");
    if (addSideBtn) {
      addSideBtn.addEventListener("click", function () {
        addSteelSideInput(line.querySelector("[data-steel-sides]"));
        recalcSteelLine(line, unit);
      });
    }
  }

  function buildSteelSides(line, count) {
    var container = line.querySelector("[data-steel-sides]");
    if (!container) return;
    container.innerHTML = "";
    for (var i = 0; i < count; i += 1) addSteelSideInput(container);
  }

  function addSteelSideInput(container) {
    var row = document.createElement("div");
    row.className = "dpr-reading-row";
    row.innerHTML =
      '<input type="number" min="0" step="0.1" data-steel-side placeholder="Side mm">' +
      '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm" data-remove-side><i class="fa-solid fa-trash"></i></button>';
    row.querySelector("input").addEventListener("input", function () {
      recalcSteelLine(container.closest("[data-dpr-steel-line]"), (getForm().querySelector("#dpr_unit_hidden") || {}).value || "");
    });
    row.querySelector("[data-remove-side]").addEventListener("click", function () {
      if (container.children.length > 1) row.remove();
      recalcSteelLine(container.closest("[data-dpr-steel-line]"), (getForm().querySelector("#dpr_unit_hidden") || {}).value || "");
    });
    container.appendChild(row);
  }

  function addManpowerRow(form) {
    var template = form.querySelector("[data-dpr-manpower-template]");
    var container = form.querySelector("[data-dpr-manpower-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-manpower-row]");
    var subSel = row.querySelector("[data-mp-subcontractor]");
    var workerSel = row.querySelector("[data-mp-worker]");
    if (subSel) {
      subSel.addEventListener("change", function () {
        loadWorkersForRow(subSel, workerSel);
      });
    }
    if (workerSel) {
      workerSel.addEventListener("change", function () {
        var nameInp = row.querySelector("[data-mp-worker-name]");
        if (workerSel.selectedOptions[0] && nameInp) {
          nameInp.value = workerSel.selectedOptions[0].textContent.replace(/^\s+|\s+$/g, "");
        }
      });
    }
    row.querySelector("[data-dpr-remove-manpower]").addEventListener("click", function () { row.remove(); });
    container.appendChild(row);
  }

  function loadWorkersForRow(subSel, workerSel) {
    if (!workerSel) return;
    workerSel.innerHTML = '<option value="">Select worker</option>';
    var subId = subSel.value;
    if (!subId) {
      workerSel.disabled = true;
      return;
    }
    workerSel.disabled = false;
    fetch("/api/subcontractors/" + subId + "/workers")
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        rows.forEach(function (w) {
          var opt = document.createElement("option");
          opt.value = w.id;
          opt.textContent = (w.worker_code ? w.worker_code + " — " : "") + (w.worker_name || "");
          workerSel.appendChild(opt);
        });
      });
  }

  function buildMeasurementPayload(form) {
    var unit = (form.querySelector("#dpr_unit_hidden") || {}).value || "";
    var ut = unitType(unit);
    if (ut === "volume") {
      return {
        lengths: collectReadings(form, "length"),
        widths: collectReadings(form, "width"),
        depths: collectReadings(form, "depth"),
      };
    }
    if (ut === "area") {
      return {
        lengths: collectReadings(form, "length"),
        widths: collectReadings(form, "width"),
      };
    }
    if (ut === "steel") {
      var lines = [];
      form.querySelectorAll("[data-dpr-steel-line]").forEach(function (line) {
        var shapeSel = line.querySelector("[data-steel-shape]");
        var opt = shapeSel && shapeSel.selectedOptions[0];
        var sides = [];
        line.querySelectorAll("[data-steel-side]").forEach(function (inp) { sides.push(inp.value); });
        lines.push({
          description: (line.querySelector("[data-steel-description]") || {}).value || "",
          num_bars: (line.querySelector("[data-steel-bars]") || {}).value || 0,
          diameter_mm: (line.querySelector("[data-steel-dia]") || {}).value || 0,
          shape_id: shapeSel ? shapeSel.value : null,
          formula_type: opt ? opt.dataset.formula : "straight",
          cutting_length: (line.querySelector("[data-steel-cutting]") || {}).value || 0,
          side_measurements: sides,
        });
      });
      return { lines: lines };
    }
    return { quantity: (form.querySelector("[data-dpr-simple-qty]") || {}).value || 0 };
  }

  function buildManpowerPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-manpower-row]").forEach(function (row) {
      rows.push({
        subcontractor_id: (row.querySelector("[data-mp-subcontractor]") || {}).value || null,
        worker_id: (row.querySelector("[data-mp-worker]") || {}).value || null,
        worker_name: (row.querySelector("[data-mp-worker-name]") || {}).value || "",
        trade_name: (row.querySelector("[data-mp-trade]") || {}).value || "",
        hours_worked: (row.querySelector("[data-mp-hours]") || {}).value || 0,
        remarks: (row.querySelector("[data-mp-remarks]") || {}).value || "",
      });
    });
    return rows;
  }

  function addMaterialRow(form) {
    var template = form.querySelector("[data-dpr-material-template]");
    var container = form.querySelector("[data-dpr-materials-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-material-row]");
    row.querySelector("[data-dpr-remove-material]").addEventListener("click", function () { row.remove(); });
    container.appendChild(row);
  }

  function addEquipmentRow(form) {
    var template = form.querySelector("[data-dpr-equipment-template]");
    var container = form.querySelector("[data-dpr-equipment-rows]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-dpr-equipment-row]");
    row.querySelector("[data-dpr-remove-equipment]").addEventListener("click", function () { row.remove(); });
    container.appendChild(row);
  }

  function buildMaterialsPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-material-row]").forEach(function (row) {
      var name = ((row.querySelector("[data-mat-name]") || {}).value || "").trim();
      if (!name) return;
      rows.push({
        material_name: name,
        quantity: (row.querySelector("[data-mat-qty]") || {}).value || 0,
        unit: (row.querySelector("[data-mat-unit]") || {}).value || "",
        remarks: (row.querySelector("[data-mat-remarks]") || {}).value || "",
      });
    });
    return rows;
  }

  function buildEquipmentPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-dpr-equipment-row]").forEach(function (row) {
      var name = ((row.querySelector("[data-eq-name]") || {}).value || "").trim();
      if (!name) return;
      rows.push({
        equipment_name: name,
        hours_used: (row.querySelector("[data-eq-hours]") || {}).value || 0,
        remarks: (row.querySelector("[data-eq-remarks]") || {}).value || "",
      });
    });
    return rows;
  }

  function loadBoqItems(form, projectId) {
    state.boqItems = [];
    if (!projectId) {
      fillBoqDropdowns(form);
      showMeasurementPanel(form, "");
      return;
    }
    fetch("/api/projects/" + projectId + "/boq-items")
      .then(function (r) { return r.json(); })
      .then(function (items) {
        state.boqItems = items || [];
        fillBoqDropdowns(form);
        var continueBoq = form.getAttribute("data-continue-boq");
        if (continueBoq) {
          var numSel = form.querySelector("[data-dpr-boq-number]");
          if (numSel) numSel.value = continueBoq;
          fillDescriptionDropdown(form, continueBoq);
          var matches = boqItemsForNumber(continueBoq);
          if (matches.length === 1) {
            selectBoqItem(form, matches[0].id);
          } else if (matches.length > 1) {
            var descId = form.getAttribute("data-continue-boq-item");
            if (descId) selectBoqItem(form, descId);
          }
        }
      });
  }

  function openShapeModal() {
    var modal = document.getElementById("dpr-new-shape-modal");
    if (modal) {
      modal.hidden = false;
      modal.setAttribute("aria-hidden", "false");
    }
  }

  function closeShapeModal() {
    var modal = document.getElementById("dpr-new-shape-modal");
    if (modal) {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
    }
  }

  function saveNewShape() {
    var name = (document.getElementById("dpr_new_shape_name") || {}).value || "";
    var sides = (document.getElementById("dpr_new_shape_sides") || {}).value || "6";
    var formula = (document.getElementById("dpr_new_shape_formula") || {}).value || "perimeter";
    if (!name.trim()) return;
    var body = new FormData();
    body.append("shape_name", name.trim());
    body.append("side_count", sides);
    body.append("formula_type", formula);
    fetch("/api/steel-shapes", { method: "POST", body: body })
      .then(function (r) { return r.json(); })
      .then(function (shape) {
        document.querySelectorAll("[data-steel-shape]").forEach(function (sel) {
          var newOpt = document.createElement("option");
          newOpt.value = shape.id;
          newOpt.textContent = shape.shape_name;
          newOpt.dataset.sides = shape.side_count;
          newOpt.dataset.formula = shape.formula_type;
          var newMarker = sel.querySelector('option[value="new"]');
          if (newMarker) sel.insertBefore(newOpt, newMarker);
          else sel.appendChild(newOpt);
        });
        if (state.pendingShapeSelect) {
          state.pendingShapeSelect.value = String(shape.id);
          state.pendingShapeSelect.dispatchEvent(new Event("change"));
          state.pendingShapeSelect = null;
        }
        closeShapeModal();
      });
  }

  function initContinueModal(form) {
    var modal = document.getElementById("dpr-continue-modal");
    if (!modal || modal.hidden) return;
    modal.querySelectorAll("[data-dpr-continue-no]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        modal.hidden = true;
        form.removeAttribute("data-continue-boq");
        form.setAttribute("data-continue-project", "");
        var descSel = form.querySelector("[data-dpr-boq-description]");
        var numSel = form.querySelector("[data-dpr-boq-number]");
        if (descSel) descSel.value = "";
        if (numSel) numSel.value = "";
        showMeasurementPanel(form, "");
      });
    });
    modal.querySelector("[data-dpr-continue-yes]").addEventListener("click", function () {
      modal.hidden = true;
      var projectId = modal.getAttribute("data-continue-project");
      var boqNum = modal.getAttribute("data-continue-boq");
      form.setAttribute("data-continue-project", projectId || "");
      form.setAttribute("data-continue-boq", boqNum || "");
      clearMeasurementFields(form);
      if (projectId) loadBoqItems(form, projectId);
    });
  }

  function clearMeasurementFields(form) {
    form.querySelectorAll("[data-dpr-readings]").forEach(function (c) { c.innerHTML = ""; });
    var steel = form.querySelector("[data-dpr-steel-lines]");
    if (steel) steel.innerHTML = "";
    var ut = unitType((form.querySelector("#dpr_unit_hidden") || {}).value || "");
    if (ut === "steel") addSteelLine(form);
    else if (ut === "volume") resetDimensionPanel(form.querySelector("[data-dpr-volume-panel]"), ut);
    else if (ut === "area") resetDimensionPanel(form.querySelector("[data-dpr-area-panel]"), ut);
    recalcQuantity(form);
  }

  function initDprForm() {
    var form = getForm();
    if (!form) return;

    var dateInp = form.querySelector("#dpr_report_date");
    if (dateInp && !dateInp.value) {
      dateInp.value = new Date().toISOString().slice(0, 10);
    }

    form.querySelector("[data-dpr-project-id]").addEventListener("change", function () {
      syncProjectDropdowns(form, "id");
    });
    form.querySelector("[data-dpr-project-name]").addEventListener("change", function () {
      syncProjectDropdowns(form, "name");
    });

    form.querySelector("[data-dpr-boq-number]").addEventListener("change", function () {
      var num = form.querySelector("[data-dpr-boq-number]").value;
      form.querySelector("#dpr_boq_number_hidden").value = num;
      fillDescriptionDropdown(form, num);
      var matches = boqItemsForNumber(num);
      if (matches.length === 1) {
        selectBoqItem(form, matches[0].id);
      } else {
        form.querySelector("[data-dpr-boq-description]").value = "";
        form.querySelector("#dpr_boq_description_hidden").value = "";
        form.querySelector("[data-dpr-unit-display]").value = "";
        form.querySelector("#dpr_unit_hidden").value = "";
        showMeasurementPanel(form, "");
      }
    });

    form.querySelector("[data-dpr-boq-description]").addEventListener("change", function () {
      var id = form.querySelector("[data-dpr-boq-description]").value;
      selectBoqItem(form, id);
    });

    form.querySelectorAll("[data-dpr-add-reading]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dim = btn.getAttribute("data-dpr-add-reading");
        var scope = btn.closest("[data-dpr-volume-panel], [data-dpr-area-panel]");
        var container = scope ? scope.querySelector('[data-dpr-readings="' + dim + '"]') : null;
        if (container) addReadingRow(container, dim);
      });
    });

    form.querySelector("[data-dpr-add-steel-line]").addEventListener("click", function () {
      addSteelLine(form);
    });

    var billClientSel = form.querySelector("[data-dpr-bill-client]");
    if (billClientSel) {
      billClientSel.addEventListener("change", function () { updateBillingMode(form); });
      updateBillingMode(form);
    }

    form.querySelector("[data-dpr-add-manpower]").addEventListener("click", function () {
      addManpowerRow(form);
    });

    var addMatBtn = form.querySelector("[data-dpr-add-material]");
    if (addMatBtn) addMatBtn.addEventListener("click", function () { addMaterialRow(form); });

    var addEqBtn = form.querySelector("[data-dpr-add-equipment]");
    if (addEqBtn) addEqBtn.addEventListener("click", function () { addEquipmentRow(form); });

    var simpleQty = form.querySelector("[data-dpr-simple-qty]");
    if (simpleQty) simpleQty.addEventListener("input", function () { recalcQuantity(form); });

    form.addEventListener("submit", function () {
      syncProjectHidden(form);
      updateBillingMode(form);
      var mpPayload = form.querySelector("[data-dpr-manpower-payload]");
      var mPayload = form.querySelector("[data-dpr-measurement-payload]");
      var matPayload = form.querySelector("[data-dpr-materials-payload]");
      var eqPayload = form.querySelector("[data-dpr-equipment-payload]");
      if (mPayload) mPayload.value = JSON.stringify(buildMeasurementPayload(form));
      if (mpPayload) mpPayload.value = JSON.stringify(buildManpowerPayload(form));
      if (matPayload) matPayload.value = JSON.stringify(buildMaterialsPayload(form));
      if (eqPayload) eqPayload.value = JSON.stringify(buildEquipmentPayload(form));
    });

    var continueProject = form.getAttribute("data-continue-project");
    if (continueProject) {
      syncProjectHidden(form);
      loadBoqItems(form, continueProject);
    }

    document.querySelectorAll("[data-dpr-shape-cancel]").forEach(function (btn) {
      btn.addEventListener("click", closeShapeModal);
    });
    var shapeSave = document.querySelector("[data-dpr-shape-save]");
    if (shapeSave) shapeSave.addEventListener("click", saveNewShape);

    initContinueModal(form);
  }

  document.addEventListener("DOMContentLoaded", initDprForm);
})();
