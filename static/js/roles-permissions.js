(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function collectRoleForm(form) {
    if (!form) return {};
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === "submit" || el.type === "button") return;
      if (el.type === "checkbox") {
        data[el.name] = el.checked ? "on" : "";
      } else if (!el.disabled) {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  function collectMatrixAssignments() {
    var rows = document.querySelectorAll("#permission-matrix-table tbody tr[data-permission-id]");
    var assignments = [];
    Array.prototype.forEach.call(rows, function (tr) {
      var permId = tr.getAttribute("data-permission-id");
      var flags = {};
      Array.prototype.forEach.call(tr.querySelectorAll(".matrix-action"), function (cb) {
        flags[cb.getAttribute("data-action")] = cb.checked;
      });
      assignments.push({ permission_id: parseInt(permId, 10), action_flags: flags });
    });
    return assignments;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var boot = window.ROLES_PERMISSIONS_BOOT || {};

    var importBtn = document.getElementById("roles-import-btn");
    var importModal = document.getElementById("roles-import-modal");
    var importClose = document.getElementById("roles-import-close");
    var importRun = document.getElementById("roles-import-run");
    var importFile = document.getElementById("roles-import-file");
    var importStatus = document.getElementById("roles-import-status");

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
        fetch("/api/roles-permissions/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " roles.";
              }
              setTimeout(function () {
                window.location.reload();
              }, 800);
            } else {
              var msg = (res.body && (res.body.error || res.body.errors)) || "Import failed.";
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

    var aiBtn = document.getElementById("role-ai-validate-btn");
    var aiStatus = document.getElementById("role-ai-status");
    var formCard = document.getElementById("role-form");
    var form = formCard ? formCard.querySelector("form") : null;

    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        fetch("/api/roles-permissions/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            role_id: boot.roleId,
            form: collectRoleForm(form),
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

    var saveMatrixBtn = document.getElementById("save-matrix-btn");
    var matrixStatus = document.getElementById("matrix-save-status");
    if (saveMatrixBtn && boot.roleId && boot.isSuperAdmin) {
      saveMatrixBtn.addEventListener("click", function () {
        if (matrixStatus) matrixStatus.textContent = "Saving…";
        fetch("/api/roles-permissions/roles/" + encodeURIComponent(boot.roleId) + "/matrix", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ assignments: collectMatrixAssignments() }),
        })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (matrixStatus) {
              matrixStatus.textContent = res.ok
                ? "Saved " + (res.body.saved || 0) + " permission mappings."
                : (res.body && res.body.error) || "Save failed.";
            }
          })
          .catch(function () {
            if (matrixStatus) matrixStatus.textContent = "Save request failed.";
          });
      });
    }
  });
})();
