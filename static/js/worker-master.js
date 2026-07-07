(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function collectWorkerForm(form) {
    if (!form) return {};
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === "submit" || el.type === "button" || el.type === "file") return;
      if (el.type === "checkbox") {
        data[el.name] = el.checked ? "on" : "";
      } else if (!el.disabled) {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  function toggleSubcontractorField() {
    var sel = document.getElementById("worker-type-select");
    var field = document.getElementById("subcontractor-field");
    if (!sel || !field) return;
    var isSub = sel.value === "Subcontractor Worker";
    field.style.display = isSub ? "" : "none";
  }

  document.addEventListener("DOMContentLoaded", function () {
    toggleSubcontractorField();
    var typeSel = document.getElementById("worker-type-select");
    if (typeSel) typeSel.addEventListener("change", toggleSubcontractorField);

    var importBtn = document.getElementById("worker-import-btn");
    var importModal = document.getElementById("worker-import-modal");
    var importClose = document.getElementById("worker-import-close");
    var importRun = document.getElementById("worker-import-run");
    var importFile = document.getElementById("worker-import-file");
    var importStatus = document.getElementById("worker-import-status");

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
        fetch("/api/worker-master/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (res.ok && res.body.ok) {
              if (importStatus) {
                importStatus.textContent = "Imported " + (res.body.imported || 0) + " workers.";
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

    var aiBtn = document.getElementById("worker-ai-validate-btn");
    var aiStatus = document.getElementById("worker-ai-status");
    var formCard = document.getElementById("worker-form");
    var form = formCard ? formCard.querySelector("form") : null;
    var boot = window.WORKER_MASTER_BOOT || {};

    if (aiBtn && form) {
      aiBtn.addEventListener("click", function () {
        if (aiStatus) aiStatus.textContent = "Validating…";
        fetch("/api/worker-master/ai/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            worker_id: boot.workerId,
            form: collectWorkerForm(form),
          }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (!aiStatus) return;
            if (data.ok) {
              var warn = (data.warnings || []).length;
              aiStatus.textContent = warn ? "OK with " + warn + " warning(s)." : "Validation passed.";
            } else {
              var issues = (data.issues || []).map(function (i) {
                return i.message;
              });
              aiStatus.textContent = issues.join(" ") || "Issues found.";
            }
          })
          .catch(function () {
            if (aiStatus) aiStatus.textContent = "Validation request failed.";
          });
      });
    }

    var faceBtn = document.getElementById("worker-face-register-btn");
    var faceInput = document.getElementById("worker-face-image");
    var faceStatus = document.getElementById("worker-face-status");
    if (faceBtn && faceInput && boot.workerId) {
      faceBtn.addEventListener("click", function () {
        if (!faceInput.files || !faceInput.files[0]) {
          if (faceStatus) faceStatus.textContent = "Capture or choose a camera image first.";
          return;
        }
        if (faceStatus) faceStatus.textContent = "Registering…";
        var fd = new FormData();
        fd.append("face_image", faceInput.files[0]);
        fetch("/api/worker-master/" + boot.workerId + "/face-registration", {
          method: "POST",
          body: fd,
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, body: j };
            });
          })
          .then(function (res) {
            if (faceStatus) {
              if (res.ok && res.body.ok) {
                faceStatus.textContent = "Face template stored: " + (res.body.template_reference || "OK");
              } else {
                faceStatus.textContent = (res.body && res.body.error) || "Registration failed.";
              }
            }
          })
          .catch(function () {
            if (faceStatus) faceStatus.textContent = "Face registration request failed.";
          });
      });
    }
  });
})();
