(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function collectDepartmentForm(form) {
    if (!form) return {};
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === "submit" || el.type === "button") return;
      if (el.type === "checkbox") {
        data[el.name] = el.checked ? "on" : "";
      } else if (!el.disabled) {
        data[el.name] = el.value;
      } else if (el.tagName === "SELECT") {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  function filterBranchOptions(companySelect, branchSelect) {
    if (!companySelect || !branchSelect) return;
    var companyId = companySelect.value;
    Array.prototype.forEach.call(branchSelect.options, function (opt) {
      if (!opt.value) {
        opt.hidden = false;
        return;
      }
      var optCompany = opt.getAttribute("data-company");
      opt.hidden = Boolean(companyId && optCompany && optCompany !== companyId);
    });
    if (branchSelect.selectedOptions.length && branchSelect.selectedOptions[0].hidden) {
      branchSelect.value = "";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var companySelect = document.getElementById("dept-company-id");
    var branchSelect = document.getElementById("dept-branch-id");
    if (companySelect && branchSelect) {
      companySelect.addEventListener("change", function () {
        filterBranchOptions(companySelect, branchSelect);
      });
      filterBranchOptions(companySelect, branchSelect);
    }

    var importBtn = document.getElementById("department-import-btn");
    var importModal = document.getElementById("department-import-modal");
    var importClose = document.getElementById("department-import-close");
    var importRun = document.getElementById("department-import-run");
    var importFile = document.getElementById("department-import-file");
    var importStatus = document.getElementById("department-import-status");

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
        fetch("/api/department-master/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " departments.";
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

    var aiBtn = document.getElementById("department-ai-validate-btn");
    var aiStatus = document.getElementById("department-ai-status");
    var formCard = document.getElementById("department-form");
    var form = formCard ? formCard.querySelector("form") : null;
    var boot = window.DEPARTMENT_MASTER_BOOT || {};

    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        fetch("/api/department-master/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            department_id: boot.departmentId,
            form: collectDepartmentForm(form),
          }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (!aiStatus) return;
            var parts = [];
            if (data.duplicates && data.duplicates.length) {
              parts.push("Duplicates: " + data.duplicates.join("; "));
            }
            if (data.missing && data.missing.length) {
              parts.push("Missing: " + data.missing.join(", "));
            }
            if (data.issues && data.issues.length) {
              parts.push("Issues: " + data.issues.join("; "));
            }
            if (data.suggestions && data.suggestions.length) {
              parts.push("Suggestions: " + data.suggestions.join("; "));
            }
            aiStatus.textContent = parts.length ? parts.join(" | ") : "No issues detected.";
          })
          .catch(function () {
            if (aiStatus) aiStatus.textContent = "AI validation request failed.";
          });
      });
    }

    var readonlyForm = document.querySelector("[data-readonly-form]");
    if (readonlyForm) {
      Array.prototype.forEach.call(readonlyForm.querySelectorAll("select[disabled]"), function (sel) {
        var hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = sel.name;
        hidden.value = sel.value;
        readonlyForm.appendChild(hidden);
      });
    }
  });
})();
