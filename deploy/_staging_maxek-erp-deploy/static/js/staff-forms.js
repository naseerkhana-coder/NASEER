(function () {
  var DEFAULT_COMPONENTS = [
    { component_name: "Room Rent", amount: 0 },
    { component_name: "Travel Expense", amount: 0 },
    { component_name: "Telephone", amount: 0 },
  ];

  function parseNum(v) {
    var n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  }

  function getForm() {
    return document.querySelector("[data-staff-form]");
  }

  function isMonthly(form) {
    var sel = form.querySelector("[data-staff-salary-type]");
    return sel && sel.value === "Monthly";
  }

  function syncCustomFieldVisibility(row) {
    var nameSel = row.querySelector("[data-component-name]");
    var customWrap = row.querySelector("[data-component-custom-wrap]");
    var customInp = row.querySelector("[data-component-custom]");
    if (!nameSel || !customWrap) return;
    var isOther = nameSel.value === "Other";
    customWrap.hidden = !isOther;
    if (customInp) {
      if (isOther) {
        customInp.required = true;
      } else {
        customInp.required = false;
        customInp.value = "";
      }
    }
  }

  function toggleMonthlyPanels(form) {
    var monthly = isMonthly(form);
    var splitPanel = form.querySelector("[data-staff-salary-split]");
    var travelPanel = form.querySelector("[data-staff-travel-panel]");
    var salaryField = form.querySelector("[data-staff-salary-total]");
    if (splitPanel) splitPanel.hidden = !monthly;
    if (travelPanel) travelPanel.hidden = !monthly;
    if (salaryField) salaryField.readOnly = monthly;
    if (monthly && !form.querySelector("[data-staff-component-row]")) {
      DEFAULT_COMPONENTS.forEach(function (c) {
        addComponentRow(form, c.component_name, c.amount);
      });
    }
    recalcSalaryTotal(form);
  }

  function addComponentRow(form, name, amount) {
    var template = form.querySelector("[data-staff-component-template]");
    var container = form.querySelector("[data-staff-components]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-staff-component-row]");
    var nameSel = row.querySelector("[data-component-name]");
    var customInp = row.querySelector("[data-component-custom]");
    var amtInp = row.querySelector("[data-component-amount]");
    if (name && nameSel) {
      var found = false;
      Array.prototype.forEach.call(nameSel.options, function (opt) {
        if (opt.value === name) {
          nameSel.value = name;
          found = true;
        }
      });
      if (!found && customInp) {
        nameSel.value = "Other";
        customInp.value = name;
      }
    }
    if (amtInp && amount !== undefined) amtInp.value = amount;
    bindComponentRow(form, row);
    syncCustomFieldVisibility(row);
    container.appendChild(row);
    recalcSalaryTotal(form);
  }

  function bindComponentRow(form, row) {
    var nameSel = row.querySelector("[data-component-name]");
    if (nameSel) {
      nameSel.addEventListener("change", function () {
        syncCustomFieldVisibility(row);
        recalcSalaryTotal(form);
      });
    }
    row.querySelectorAll("[data-component-amount], [data-component-custom]").forEach(function (el) {
      el.addEventListener("input", function () { recalcSalaryTotal(form); });
    });
    var removeBtn = row.querySelector("[data-staff-remove-component]");
    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        row.remove();
        recalcSalaryTotal(form);
      });
    }
  }

  function componentNameFromRow(row) {
    var nameSel = row.querySelector("[data-component-name]");
    var customInp = row.querySelector("[data-component-custom]");
    if (!nameSel) return "";
    if (nameSel.value === "Other" && customInp) {
      return (customInp.value || "").trim();
    }
    return (nameSel.value || "").trim();
  }

  function recalcSalaryTotal(form) {
    if (!isMonthly(form)) return;
    var total = 0;
    form.querySelectorAll("[data-staff-component-row]").forEach(function (row) {
      total += parseNum((row.querySelector("[data-component-amount]") || {}).value);
    });
    var salaryField = form.querySelector("[data-staff-salary-total]");
    if (salaryField) salaryField.value = total > 0 ? total.toFixed(2) : "";
    var display = form.querySelector("[data-staff-salary-total-display]");
    if (display) display.textContent = total.toFixed(2);
  }

  function buildComponentsPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-staff-component-row]").forEach(function (row) {
      var name = componentNameFromRow(row);
      if (!name) return;
      rows.push({
        component_name: name,
        amount: (row.querySelector("[data-component-amount]") || {}).value || 0,
      });
    });
    return rows;
  }

  function addTravelTierRow(form, months, mode, amount) {
    var template = form.querySelector("[data-staff-travel-template]");
    var container = form.querySelector("[data-staff-travel-tiers]");
    if (!template || !container) return;
    var row = template.content.cloneNode(true).querySelector("[data-staff-travel-row]");
    var monthsInp = row.querySelector("[data-travel-months]");
    var modeSel = row.querySelector("[data-travel-mode]");
    var amtInp = row.querySelector("[data-travel-amount]");
    if (monthsInp && months !== undefined) monthsInp.value = months;
    if (modeSel && mode) modeSel.value = mode;
    if (amtInp && amount !== undefined) amtInp.value = amount;
    row.querySelector("[data-staff-remove-travel]").addEventListener("click", function () {
      row.remove();
    });
    container.appendChild(row);
  }

  function buildTravelPayload(form) {
    var rows = [];
    form.querySelectorAll("[data-staff-travel-row]").forEach(function (row) {
      var months = parseInt((row.querySelector("[data-travel-months]") || {}).value, 10) || 0;
      if (months <= 0) return;
      rows.push({
        continuous_months: months,
        travel_mode: (row.querySelector("[data-travel-mode]") || {}).value || "One Side",
        allowance_amount: (row.querySelector("[data-travel-amount]") || {}).value || 0,
      });
    });
    return rows;
  }

  function loadInitialData(form) {
    var compRaw = form.getAttribute("data-initial-components");
    var travelRaw = form.getAttribute("data-initial-travel");
    var components = [];
    var tiers = [];
    try { components = JSON.parse(compRaw || "[]"); } catch (e) { components = []; }
    try { tiers = JSON.parse(travelRaw || "[]"); } catch (e) { tiers = []; }
    var container = form.querySelector("[data-staff-components]");
    if (container) container.innerHTML = "";
    if (components.length) {
      components.forEach(function (c) {
        addComponentRow(form, c.component_name, c.amount);
      });
    }
    var travelContainer = form.querySelector("[data-staff-travel-tiers]");
    if (travelContainer) travelContainer.innerHTML = "";
    if (tiers.length) {
      tiers.forEach(function (t) {
        addTravelTierRow(form, t.continuous_months, t.travel_mode, t.allowance_amount);
      });
    }
    toggleMonthlyPanels(form);
  }

  function initStaffForm() {
    var form = getForm();
    if (!form) return;

    var salaryType = form.querySelector("[data-staff-salary-type]");
    if (salaryType) {
      salaryType.addEventListener("change", function () { toggleMonthlyPanels(form); });
    }

    var addComp = form.querySelector("[data-staff-add-component]");
    if (addComp) {
      addComp.addEventListener("click", function () { addComponentRow(form, "Basic Salary", 0); });
    }

    var addTravel = form.querySelector("[data-staff-add-travel]");
    if (addTravel) {
      addTravel.addEventListener("click", function () {
        addTravelTierRow(form, 3, "One Side", 0);
      });
    }

    form.addEventListener("submit", function () {
      var compPayload = form.querySelector("[data-staff-components-payload]");
      var travelPayload = form.querySelector("[data-staff-travel-payload]");
      if (compPayload) compPayload.value = JSON.stringify(buildComponentsPayload(form));
      if (travelPayload) travelPayload.value = JSON.stringify(buildTravelPayload(form));
      recalcSalaryTotal(form);
    });

    loadInitialData(form);
  }

  document.addEventListener("DOMContentLoaded", initStaffForm);
})();
