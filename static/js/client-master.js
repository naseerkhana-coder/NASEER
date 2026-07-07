(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function collectClientForm(form) {
    if (!form) return {};
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === "submit" || el.type === "button" || el.type === "file") return;
      if (el.type === "checkbox") {
        data[el.name] = el.checked ? "on" : "";
      } else if (el.type === "radio") {
        if (el.checked) data[el.name] = el.value;
      } else if (el.name.indexOf("[]") > -1) {
        if (!data[el.name]) data[el.name] = [];
        data[el.name].push(el.value);
      } else if (!el.disabled) {
        data[el.name] = el.value;
      } else if (el.tagName === "SELECT") {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  function bindRepeatRows(addBtnId, containerId, html) {
    var addBtn = document.getElementById(addBtnId);
    var container = document.getElementById(containerId);
    if (!addBtn || !container) return;
    addBtn.addEventListener("click", function () {
      var wrap = document.createElement("div");
      wrap.innerHTML = html.trim();
      var row = wrap.firstChild;
      container.appendChild(row);
      var radios = row.querySelectorAll('input[type="radio"]');
      if (radios.length) {
        var idx = container.querySelectorAll(".client-repeat-row").length - 1;
        radios[0].value = String(idx);
      }
      var removeBtn = row.querySelector(".client-remove-row");
      if (removeBtn) {
        removeBtn.addEventListener("click", function () {
          row.remove();
        });
      }
    });
    container.addEventListener("click", function (e) {
      if (e.target && e.target.classList.contains("client-remove-row")) {
        var row = e.target.closest(".client-repeat-row");
        if (row) row.remove();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindRepeatRows(
      "client-add-contact",
      "client-contacts-rows",
      '<div class="client-repeat-row" style="display:grid;grid-template-columns:repeat(5,1fr) auto;gap:0.5rem;margin-bottom:0.5rem;align-items:end;">' +
        '<input type="hidden" name="contact_id[]" value="">' +
        '<input name="contact_name[]" placeholder="Name">' +
        '<input name="contact_designation[]" placeholder="Designation">' +
        '<input name="contact_email[]" placeholder="Email">' +
        '<input name="contact_mobile[]" placeholder="Mobile">' +
        '<label style="font-size:0.8rem;"><input type="radio" name="contact_primary_index" value="0"> Primary</label>' +
        '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm client-remove-row">×</button>' +
        "</div>"
    );

    bindRepeatRows(
      "client-add-address",
      "client-addresses-rows",
      '<div class="client-repeat-row" style="display:grid;grid-template-columns:100px 1fr 1fr 1fr 80px auto;gap:0.5rem;margin-bottom:0.5rem;align-items:end;">' +
        '<input type="hidden" name="address_id[]" value="">' +
        '<select name="address_type[]"><option>Billing</option><option>Site</option><option>Other</option></select>' +
        '<input name="address_line1[]" placeholder="Address line">' +
        '<input name="address_city[]" placeholder="City">' +
        '<input name="address_state[]" placeholder="State">' +
        '<input name="address_pin_code[]" placeholder="PIN">' +
        '<label style="font-size:0.8rem;"><input type="radio" name="address_primary_index" value="0"> Primary</label>' +
        '<button type="button" class="erp-btn erp-btn-ghost erp-btn-sm client-remove-row">×</button>' +
        "</div>"
    );

    var importBtn = document.getElementById("client-import-btn");
    var importModal = document.getElementById("client-import-modal");
    var importClose = document.getElementById("client-import-close");
    var importRun = document.getElementById("client-import-run");
    var importFile = document.getElementById("client-import-file");
    var importStatus = document.getElementById("client-import-status");

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
        fetch("/api/client-master/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " clients.";
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

    var aiBtn = document.getElementById("client-ai-validate-btn");
    var aiStatus = document.getElementById("client-ai-status");
    var formCard = document.getElementById("client-form");
    var form = formCard ? formCard.querySelector("form") : null;
    var boot = window.CLIENT_MASTER_BOOT || {};

    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        fetch("/api/client-master/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            client_id: boot.clientId,
            form: collectClientForm(form),
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
