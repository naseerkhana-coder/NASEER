(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function collectVendorForm(form) {
    if (!form) return {};
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === "submit" || el.type === "button") return;
      if (el.type === "checkbox") {
        if (el.name === "vendor_types[]") {
          if (!data["vendor_types[]"]) data["vendor_types[]"] = [];
          if (el.checked) data["vendor_types[]"].push(el.value);
        } else {
          data[el.name] = el.checked ? "on" : "";
        }
      } else if (!el.disabled) {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var importBtn = document.getElementById("vendor-import-btn");
    var importModal = document.getElementById("vendor-import-modal");
    var importClose = document.getElementById("vendor-import-close");
    var importRun = document.getElementById("vendor-import-run");
    var importFile = document.getElementById("vendor-import-file");
    var importStatus = document.getElementById("vendor-import-status");

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
        fetch("/api/vendor-master/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " vendors.";
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

    var aiBtn = document.getElementById("vendor-ai-validate-btn");
    var aiStatus = document.getElementById("vendor-ai-status");
    var formCard = document.getElementById("vendor-form");
    var form = formCard ? formCard.querySelector("form") : null;
    var boot = window.VENDOR_MASTER_BOOT || {};

    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        fetch("/api/vendor-master/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            vendor_id: boot.vendorId,
            form: collectVendorForm(form),
          }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (!aiStatus) return;
            if (data.ok) {
              aiStatus.textContent = "Validation passed.";
              aiStatus.style.color = "var(--erp-success, green)";
            } else {
              var parts = []
                .concat(data.issues || [])
                .concat(data.duplicates || [])
                .concat(data.suggestions || []);
              aiStatus.textContent = parts.slice(0, 3).join(" · ") || "Review required.";
              aiStatus.style.color = "var(--erp-warn, #b45309)";
            }
          })
          .catch(function () {
            if (aiStatus) aiStatus.textContent = "AI validation unavailable.";
          });
      });
    }
  });
})();
