(function () {
  "use strict";

  function recalcRow(row) {
    var qty = parseFloat(row.querySelector(".boq-qty")?.value || 0) || 0;
    var rate = parseFloat(row.querySelector(".boq-rate")?.value || 0) || 0;
    var executed = parseFloat(row.querySelector('[name="executed_quantity[]"]')?.value || 0) || 0;
    var amountInput = row.querySelector(".boq-amount");
    var balanceCell = row.querySelector(".boq-balance");
    var amount = Math.round(qty * rate * 100) / 100;
    if (amountInput) amountInput.value = amount.toFixed(2);
    if (balanceCell) balanceCell.textContent = Math.max(qty - executed, 0).toFixed(4);
  }

  function renumberRows(tbody) {
    Array.prototype.forEach.call(tbody.querySelectorAll(".boq-item-row"), function (row, idx) {
      row.querySelector("td").textContent = String(idx + 1);
    });
  }

  function bindRow(row) {
    ["input", "change"].forEach(function (evt) {
      row.addEventListener(evt, function (e) {
        if (e.target.classList.contains("boq-qty") || e.target.classList.contains("boq-rate")) {
          recalcRow(row);
        }
      });
    });
    var removeBtn = row.querySelector(".boq-remove-line");
    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        var tbody = row.parentElement;
        if (tbody.querySelectorAll(".boq-item-row").length <= 1) return;
        row.remove();
        renumberRows(tbody);
      });
    }
  }

  function addLine(tbody, boot) {
    var count = tbody.querySelectorAll(".boq-item-row").length;
    if (count >= (boot.maxLines || 500)) return;
    var tr = document.createElement("tr");
    tr.className = "boq-item-row";
    var unitOptions = (boot.units || ["Nos"]).map(function (u) {
      return '<option value="' + u + '">' + u + "</option>";
    }).join("");
    tr.innerHTML =
      "<td>" + (count + 1) + "</td>" +
      '<td><input name="item_number[]" value="BOQ' + (count + 1) + '"></td>' +
      '<td><input name="item_description[]"></td>' +
      '<td><input name="specification[]"></td>' +
      '<td><select name="unit[]">' + unitOptions + "</select></td>" +
      '<td><input name="quantity[]" type="number" step="0.0001" min="0" class="boq-qty"></td>' +
      '<td><input name="rate[]" type="number" step="0.01" min="0" class="boq-rate"></td>' +
      '<td><input name="amount[]" type="number" step="0.01" min="0" class="boq-amount" readonly></td>' +
      '<td><input name="executed_quantity[]" type="number" step="0.0001" min="0" value="0" readonly></td>' +
      '<td class="boq-balance">0</td>' +
      '<td><button type="button" class="erp-btn erp-btn-ghost erp-btn-sm boq-remove-line">&times;</button></td>';
    tbody.appendChild(tr);
    bindRow(tr);
  }

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var boot = window.BOQ_MANAGEMENT_BOOT || {};
    var tbody = document.getElementById("boq-items-body");
    if (tbody) {
      Array.prototype.forEach.call(tbody.querySelectorAll(".boq-item-row"), function (row) {
        bindRow(row);
        recalcRow(row);
      });
    }
    var addBtn = document.getElementById("boq-add-line");
    if (addBtn && tbody) {
      addBtn.addEventListener("click", function () {
        addLine(tbody, boot);
      });
    }

    var importBtn = document.getElementById("boq-import-btn");
    var importModal = document.getElementById("boq-import-modal");
    var importClose = document.getElementById("boq-import-close");
    var importRun = document.getElementById("boq-import-run");
    var importFile = document.getElementById("boq-import-file");
    var importStatus = document.getElementById("boq-import-status");
    var importProject = document.getElementById("boq-import-project");
    var importName = document.getElementById("boq-import-name");

    if (importBtn) importBtn.addEventListener("click", function () { showImportModal(importModal, true); });
    if (importClose) importClose.addEventListener("click", function () { showImportModal(importModal, false); });
    if (importRun && importFile) {
      importRun.addEventListener("click", function () {
        if (!importFile.files || !importFile.files[0]) {
          if (importStatus) importStatus.textContent = "Choose a file first.";
          return;
        }
        if (importStatus) importStatus.textContent = "Importing…";
        var fd = new FormData();
        fd.append("file", importFile.files[0]);
        if (importProject) fd.append("project_id", importProject.value);
        if (importName) fd.append("boq_name", importName.value);
        fetch("/api/boq-management/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) importStatus.textContent = "Imported BOQ " + (res.body.boq_number || "") + ".";
              setTimeout(function () {
                window.location.href = "/boq-management?boq_id=" + (res.body.boq_id || "");
              }, 600);
            } else {
              if (importStatus) importStatus.textContent = res.body.error || "Import failed.";
            }
          })
          .catch(function () {
            if (importStatus) importStatus.textContent = "Import request failed.";
          });
      });
    }

    var aiBtn = document.getElementById("boq-ai-validate-btn");
    var aiStatus = document.getElementById("boq-ai-status");
    if (aiBtn) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        fetch("/api/boq-management/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ boq_id: boot.boqId }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!aiStatus) return;
            if (data.ok) {
              var warn = (data.warnings || []).length;
              aiStatus.textContent = warn ? "OK with " + warn + " warning(s)." : "Validation passed.";
            } else {
              var issues = (data.issues || []).map(function (i) { return i.message; });
              aiStatus.textContent = issues.join(" ") || "Issues found.";
            }
          })
          .catch(function () {
            if (aiStatus) aiStatus.textContent = "Validation request failed.";
          });
      });
    }
  });
})();
