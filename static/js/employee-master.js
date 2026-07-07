(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function filterByCompany(companySelect, selects) {
    if (!companySelect) return;
    var companyId = companySelect.value;
    selects.forEach(function (sel) {
      if (!sel) return;
      Array.prototype.forEach.call(sel.options, function (opt) {
        if (!opt.value) {
          opt.hidden = false;
          return;
        }
        var optCompany = opt.getAttribute("data-company");
        opt.hidden = Boolean(companyId && optCompany && optCompany !== companyId);
      });
      if (sel.selectedOptions.length && sel.selectedOptions[0].hidden) {
        sel.value = "";
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var companySelect = document.getElementById("emp-company-id");
    var branchSelect = document.getElementById("emp-branch-id");
    var deptSelect = document.getElementById("emp-dept-id");
    var desigSelect = document.getElementById("emp-desig-id");
    if (companySelect) {
      companySelect.addEventListener("change", function () {
        filterByCompany(companySelect, [branchSelect, deptSelect, desigSelect]);
      });
      filterByCompany(companySelect, [branchSelect, deptSelect, desigSelect]);
    }

    var ecRows = document.getElementById("emergency-contacts-rows");
    var addEc = document.getElementById("employee-add-ec");
    if (addEc && ecRows) {
      addEc.addEventListener("click", function () {
        var row = document.createElement("div");
        row.className = "employee-repeat-row";
        row.style.cssText =
          "display:grid;grid-template-columns:repeat(5,1fr) auto;gap:0.5rem;margin-bottom:0.5rem;";
        row.innerHTML =
          '<input type="hidden" name="ec_id[]" value="">' +
          '<input name="contact_name[]" placeholder="Name">' +
          '<input name="relationship[]" placeholder="Relationship">' +
          '<input name="phone[]" placeholder="Phone">' +
          '<input name="email[]" placeholder="Email">' +
          '<input name="address[]" placeholder="Address">' +
          '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm employee-remove-row">×</button>';
        ecRows.appendChild(row);
      });
      ecRows.addEventListener("click", function (e) {
        if (e.target && e.target.classList.contains("employee-remove-row")) {
          var rows = ecRows.querySelectorAll(".employee-repeat-row");
          if (rows.length > 1) e.target.closest(".employee-repeat-row").remove();
        }
      });
    }

    var importBtn = document.getElementById("employee-import-btn");
    var importModal = document.getElementById("employee-import-modal");
    var importClose = document.getElementById("employee-import-close");
    var importRun = document.getElementById("employee-import-run");
    var importFile = document.getElementById("employee-import-file");
    var importStatus = document.getElementById("employee-import-status");

    if (importBtn) {
      importBtn.addEventListener("click", function () {
        showImportModal(importModal, true);
      });
    }
    if (importClose) {
      importClose.addEventListener("click", function () {
        showImportModal(importModal, false);
      });
    }
    if (importRun && importFile) {
      importRun.addEventListener("click", function () {
        if (!importFile.files || !importFile.files[0]) {
          if (importStatus) importStatus.textContent = "Choose a file first.";
          return;
        }
        if (importStatus) importStatus.textContent = "Importing…";
        var fd = new FormData();
        fd.append("file", importFile.files[0]);
        fetch("/api/employee-master/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " employees.";
              }
              setTimeout(function () {
                window.location.reload();
              }, 800);
            } else {
              var msg =
                (res.body && (res.body.error || (res.body.errors && res.body.errors.length))) ||
                "Import failed.";
              if (importStatus) {
                importStatus.textContent = typeof msg === "string" ? msg : "Validation failed.";
              }
            }
          })
          .catch(function () {
            if (importStatus) importStatus.textContent = "Import request failed.";
          });
      });
    }

    var aiBtn = document.getElementById("employee-ai-validate-btn");
    var aiStatus = document.getElementById("employee-ai-status");
    if (aiBtn) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        var form = aiBtn.closest("form");
        var fd = new FormData(form);
        var payload = { staff_id: window.EMPLOYEE_MASTER_BOOT.staffId, form: {} };
        fd.forEach(function (v, k) {
          payload.form[k] = v;
        });
        fetch("/api/employee-master/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            var parts = [];
            if (data.issues && data.issues.length) parts.push("Issues: " + data.issues.join("; "));
            if (data.duplicates && data.duplicates.length) {
              parts.push("Duplicates: " + data.duplicates.join("; "));
            }
            if (data.missing_documents && data.missing_documents.length) {
              parts.push("Missing docs: " + data.missing_documents.join(", "));
            }
            if (data.suggestions && data.suggestions.length) {
              parts.push(data.suggestions.join(" "));
            }
            if (aiStatus) {
              aiStatus.textContent = parts.length ? parts.join(" | ") : "No issues found.";
            }
          })
          .catch(function () {
            if (aiStatus) aiStatus.textContent = "Validation failed.";
          });
      });
    }
  });
})();
