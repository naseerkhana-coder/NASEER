(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function filterByCompany(companySelect, targetSelect) {
    if (!companySelect || !targetSelect) return;
    var companyId = companySelect.value;
    Array.prototype.forEach.call(targetSelect.options, function (opt) {
      if (!opt.value) {
        opt.hidden = false;
        return;
      }
      var optCompany = opt.getAttribute("data-company");
      opt.hidden = Boolean(companyId && optCompany && optCompany !== companyId);
    });
    if (targetSelect.selectedOptions.length && targetSelect.selectedOptions[0].hidden) {
      targetSelect.value = "";
    }
  }

  function syncAdminRole() {
    var workflowRole = document.getElementById("user-workflow-role");
    var systemRole = document.getElementById("user-system-role");
    if (!workflowRole || !systemRole) return;
    if (workflowRole.value === "Administrator") {
      systemRole.value = "Admin";
      systemRole.disabled = true;
    } else if (!document.getElementById("user-master-form")?.dataset.readonly) {
      systemRole.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var companySelect = document.getElementById("user-company-id");
    var branchSelect = document.getElementById("user-branch-id");
    var deptSelect = document.getElementById("user-department-id");
    if (companySelect) {
      companySelect.addEventListener("change", function () {
        filterByCompany(companySelect, branchSelect);
        filterByCompany(companySelect, deptSelect);
      });
      filterByCompany(companySelect, branchSelect);
      filterByCompany(companySelect, deptSelect);
    }

    var workflowRole = document.getElementById("user-workflow-role");
    if (workflowRole) {
      workflowRole.addEventListener("change", syncAdminRole);
      syncAdminRole();
    }

    var form = document.getElementById("user-master-form");
    if (form && !form.dataset.readonly) {
      form.addEventListener("submit", function (e) {
        var pwd = document.getElementById("user-password");
        var confirm = document.getElementById("user-confirm-password");
        if (!pwd || !confirm) return;
        if (!pwd.value && !confirm.value) return;
        if (pwd.value !== confirm.value) {
          e.preventDefault();
          alert("Password and confirmation do not match.");
          confirm.focus();
          return;
        }
        if (pwd.value.length < 8) {
          e.preventDefault();
          alert("Password must be at least 8 characters with upper, lower, number, and special character.");
          pwd.focus();
        }
      });
    }

    var aiBtn = document.getElementById("user-ai-validate-btn");
    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        var data = {};
        Array.prototype.forEach.call(form.elements, function (el) {
          if (el.name && !el.disabled) data[el.name] = el.value;
        });
        fetch("/api/user-management/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ form: data, user_id: data.user_id || null }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (res) {
            var parts = [];
            (res.issues || []).forEach(function (x) {
              parts.push("Issue: " + x);
            });
            (res.duplicates || []).forEach(function (x) {
              parts.push("Duplicate: " + x);
            });
            (res.suggestions || []).forEach(function (x) {
              parts.push("Suggestion: " + x);
            });
            alert(parts.length ? parts.join("\n") : "Validation passed.");
          })
          .catch(function () {
            alert("AI validation unavailable.");
          });
      });
    }

    var photoBtn = document.getElementById("user-photo-btn");
    var photoInput = document.getElementById("user-photo-input");
    if (photoBtn && photoInput && form) {
      photoBtn.addEventListener("click", function () {
        photoInput.click();
      });
      photoInput.addEventListener("change", function () {
        if (!photoInput.files || !photoInput.files[0]) return;
        var uidInput = form.querySelector('input[name="user_id"]');
        if (!uidInput) return;
        var fd = new FormData();
        fd.append("photo", photoInput.files[0]);
        fetch("/api/user-management/" + uidInput.value + "/photo", {
          method: "POST",
          body: fd,
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (res) {
            if (res.ok) window.location.reload();
            else alert(res.error || "Upload failed.");
          });
      });
    }

    var resetBtn = document.getElementById("user-reset-password-btn");
    if (resetBtn && form) {
      resetBtn.addEventListener("click", function () {
        var uidInput = form.querySelector('input[name="user_id"]');
        if (!uidInput) return;
        var pwd = prompt("Enter new password for this user:");
        if (!pwd) return;
        fetch("/api/user-management/" + uidInput.value + "/reset-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ new_password: pwd }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (res) {
            alert(res.ok ? "Password reset." : res.error || "Reset failed.");
          });
      });
    }

    var importBtn = document.getElementById("user-import-btn");
    var importModal = document.getElementById("user-import-modal");
    var importClose = document.getElementById("user-import-close");
    var importRun = document.getElementById("user-import-run");
    var importFile = document.getElementById("user-import-file");
    var importStatus = document.getElementById("user-import-status");
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
        fetch("/api/user-management/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " users.";
              }
              setTimeout(function () {
                window.location.reload();
              }, 800);
            } else if (importStatus) {
              importStatus.textContent = (res.body && res.body.error) || "Import failed.";
            }
          });
      });
    }
  });
})();
