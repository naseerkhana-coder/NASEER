(function () {
  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function showStep(modal, step) {
    modal.querySelectorAll("[data-import-step]").forEach(function (el) {
      el.hidden = el.getAttribute("data-import-step") !== String(step);
    });
    var errBox = qs("[data-import-errors]", modal);
    if (errBox) {
      errBox.hidden = true;
      errBox.innerHTML = "";
    }
  }

  function renderErrors(container, errors) {
    if (!errors || !errors.length) {
      container.hidden = true;
      return;
    }
    var html = "<table class=\"erp-table erp-table-module\"><thead><tr><th>Row</th><th>Column</th><th>Error</th><th>Suggested Fix</th></tr></thead><tbody>";
    errors.forEach(function (e) {
      html += "<tr><td>" + (e.row || "—") + "</td><td>" + (e.column || "—") + "</td><td>" + (e.error || "") + "</td><td>" + (e.suggested_fix || "") + "</td></tr>";
    });
    html += "</tbody></table>";
    container.innerHTML = html;
    container.hidden = false;
  }

  function renderPreview(container, rows) {
    if (!rows || !rows.length) {
      container.innerHTML = "<p>No preview rows.</p>";
      return;
    }
    var cols = ["item_no", "boq_code", "description", "specification", "unit", "quantity", "rate", "amount", "remarks"];
    var html = "<div class=\"erp-table-scroll\"><table class=\"erp-table erp-table-module\"><thead><tr>";
    cols.forEach(function (c) {
      html += "<th>" + c.replace(/_/g, " ") + "</th>";
    });
    html += "</tr></thead><tbody>";
    rows.slice(0, 50).forEach(function (row) {
      html += "<tr>";
      cols.forEach(function (c) {
        var val = row[c] != null ? row[c] : (row.item_description && c === "description" ? row.item_description : "");
        html += "<td>" + (val != null ? val : "") + "</td>";
      });
      html += "</tr>";
    });
    html += "</tbody></table></div>";
    if (rows.length > 50) {
      html += "<p class=\"erp-hint\">Showing first 50 of " + rows.length + " rows.</p>";
    }
    container.innerHTML = html;
  }

  function initBoqImportModal() {
    var modal = document.getElementById("boq-import-modal");
    if (!modal) return;

    var openBtn = document.querySelector("[data-boq-import-open]");
    var fileInput = qs("[data-import-file]", modal);
    var projectSelect = qs("[data-import-project]", modal);
    var validateBtn = qs("[data-import-validate]", modal);
    var saveBtn = qs("[data-import-save]", modal);
    var errBox = qs("[data-import-errors]", modal);
    var previewBox = qs("[data-import-preview]", modal);
    var statusEl = qs("[data-import-status]", modal);
    var parsedRows = [];

    function openModal() {
      modal.hidden = false;
      modal.setAttribute("aria-hidden", "false");
      showStep(modal, 1);
      parsedRows = [];
      if (saveBtn) saveBtn.disabled = true;
    }

    function closeModal() {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
    }

    if (openBtn) {
      openBtn.addEventListener("click", openModal);
    }
    modal.querySelectorAll("[data-modal-close]").forEach(function (btn) {
      btn.addEventListener("click", closeModal);
    });

    if (validateBtn) {
      validateBtn.addEventListener("click", function () {
        if (!fileInput || !fileInput.files || !fileInput.files[0]) {
          window.alert("Choose an Excel or CSV file first.");
          return;
        }
        if (!projectSelect || !projectSelect.value) {
          window.alert("Select a project for this BOQ import.");
          return;
        }
        var fd = new FormData();
        fd.append("file", fileInput.files[0]);
        fd.append("project_id", projectSelect.value);
        if (statusEl) statusEl.textContent = "Validating…";
        fetch("/api/bulk-import/boq/validate", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (statusEl) statusEl.textContent = "";
            if (data.errors && data.errors.length) {
              renderErrors(errBox, data.errors);
              parsedRows = [];
              if (saveBtn) saveBtn.disabled = true;
              showStep(modal, 2);
              return;
            }
            parsedRows = data.parsed_rows || data.preview || [];
            renderPreview(previewBox, parsedRows);
            if (saveBtn) saveBtn.disabled = !parsedRows.length;
            showStep(modal, 2);
          })
          .catch(function () {
            if (statusEl) statusEl.textContent = "Validation failed.";
          });
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        if (!parsedRows.length) return;
        if (!projectSelect || !projectSelect.value) return;
        var fd = new FormData();
        fd.append("project_id", projectSelect.value);
        fd.append("parsed_rows", JSON.stringify(parsedRows));
        if (fileInput && fileInput.files && fileInput.files[0]) {
          fd.append("file", fileInput.files[0]);
        }
        if (statusEl) statusEl.textContent = "Saving…";
        saveBtn.disabled = true;
        fetch("/api/bulk-import/boq/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
          .then(function (result) {
            if (statusEl) statusEl.textContent = "";
            if (!result.ok || !result.data.ok) {
              renderErrors(errBox, result.data.errors || [{ row: "—", column: "Save", error: result.data.error || result.data.message || "Save failed.", suggested_fix: "" }]);
              saveBtn.disabled = false;
              return;
            }
            showStep(modal, 3);
            var msg = qs("[data-import-success]", modal);
            if (msg) {
              msg.textContent = "BOQ " + (result.data.boq_number || "") + " created with " + (result.data.line_count || 0) + " line(s).";
            }
            var viewLink = qs("[data-import-view]", modal);
            if (viewLink && result.data.boq_id) {
              viewLink.href = "/boq-management?view=" + result.data.boq_id;
            }
          })
          .catch(function () {
            if (statusEl) statusEl.textContent = "Save failed.";
            saveBtn.disabled = false;
          });
      });
    }
  }

  function initLibraryPicker() {
    var select = document.querySelector("[data-boq-library-select]");
    var form = document.querySelector("[data-boq-form]");
    if (!select || !form) return;
    var container = form.querySelector("[data-boq-rows]");
    var template = form.querySelector("[data-boq-row-template]");
    if (!container || !template) return;

    select.addEventListener("change", function () {
      var id = select.value;
      if (!id) return;
      fetch("/api/boq-library/" + encodeURIComponent(id), { credentials: "same-origin" })
        .then(function (res) { return res.json(); })
        .then(function (item) {
          var row = container.querySelector("[data-boq-row]");
          if (!row) {
            row = template.cloneNode(true);
            row.hidden = false;
            row.removeAttribute("data-boq-row-template");
            row.setAttribute("data-boq-row", "");
            container.appendChild(row);
          }
          var desc = row.querySelector(".boq-desc");
          if (desc) {
            var text = item.description || "";
            if (item.detailed_specification) {
              text += (text ? "\n" : "") + item.detailed_specification;
            }
            desc.value = text;
          }
          var unitSel = row.querySelector(".boq-unit");
          if (unitSel && item.unit) unitSel.value = item.unit;
          var rate = row.querySelector(".boq-rate");
          if (rate && item.standard_rate != null) rate.value = item.standard_rate;
          select.value = "";
          if (typeof form.dispatchEvent === "function") {
            form.dispatchEvent(new Event("input", { bubbles: true }));
          }
        })
        .catch(function () {});
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initBoqImportModal();
    initLibraryPicker();
  });
})();
