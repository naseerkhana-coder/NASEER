(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function collectBranchForm(form) {
    if (!form) return {};
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === "submit" || el.type === "button") return;
      if (el.type === "checkbox") {
        data[el.name] = el.checked ? "on" : "";
      } else if (el.tagName === "SELECT" && el.disabled) {
        data[el.name] = el.value;
      } else if (!el.disabled) {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var importBtn = document.getElementById("branch-import-btn");
    var importModal = document.getElementById("branch-import-modal");
    var importClose = document.getElementById("branch-import-close");
    var importRun = document.getElementById("branch-import-run");
    var importFile = document.getElementById("branch-import-file");
    var importStatus = document.getElementById("branch-import-status");

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
        fetch("/api/branch-master/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " branches.";
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

    var aiBtn = document.getElementById("branch-ai-validate-btn");
    var aiStatus = document.getElementById("branch-ai-status");
    var formCard = document.getElementById("branch-form");
    var form = formCard ? formCard.querySelector("form") : null;
    var boot = window.BRANCH_MASTER_BOOT || {};

    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        var payload = {
          branch_id: boot.branchId,
          form: collectBranchForm(form),
        };
        fetch("/api/branch-master/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify(payload),
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
            if (data.address_issues && data.address_issues.length) {
              parts.push("Address: " + data.address_issues.join("; "));
            }
            if (data.suggestions && data.suggestions.length) {
              parts.push("Suggestions: " + data.suggestions.join("; "));
            }
            if (data.ok && !parts.length) {
              aiStatus.textContent = "No issues detected.";
            } else {
              aiStatus.textContent = parts.join(" | ") || data.message || "Validation complete.";
            }
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
