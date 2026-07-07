(function () {
  "use strict";

  function showImportModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var importBtn = document.getElementById("project-import-btn");
    var modal = document.getElementById("project-import-modal");
    var closeBtn = document.getElementById("project-import-close");
    var validateBtn = document.getElementById("project-import-validate");
    var saveBtn = document.getElementById("project-import-save");
    var fileInput = document.getElementById("project-import-file");
    var resultEl = document.getElementById("project-import-result");

    if (importBtn && modal) {
      importBtn.addEventListener("click", function () {
        showImportModal(modal, true);
      });
    }
    if (closeBtn && modal) {
      closeBtn.addEventListener("click", function () {
        showImportModal(modal, false);
      });
    }

    function postImport(url) {
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (resultEl) resultEl.textContent = "Select a file first.";
        return;
      }
      var fd = new FormData();
      fd.append("file", fileInput.files[0]);
      fetch(url, { method: "POST", body: fd, credentials: "same-origin" })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (resultEl) {
            resultEl.textContent = data.error || data.message || JSON.stringify(data);
          }
          if (data.ok && url.indexOf("save") > -1) {
            window.location.reload();
          }
        })
        .catch(function (err) {
          if (resultEl) resultEl.textContent = String(err);
        });
    }

    if (validateBtn) {
      validateBtn.addEventListener("click", function () {
        postImport("/api/project-master/import/validate");
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        postImport("/api/project-master/import/save");
      });
    }

    var companySelect = document.getElementById("proj-company-id");
    var branchSelect = document.getElementById("proj-branch-id");
    if (companySelect && branchSelect && !branchSelect.dataset.static) {
      companySelect.addEventListener("change", function () {
        var cid = companySelect.value;
        if (!cid) return;
        fetch("/api/branches?company_id=" + encodeURIComponent(cid), { credentials: "same-origin" })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            var items = data.items || data.branches || [];
            branchSelect.innerHTML = '<option value="">— Select Branch —</option>';
            items.forEach(function (br) {
              var opt = document.createElement("option");
              opt.value = br.id;
              opt.textContent = (br.branch_code || "") + " — " + (br.branch_name || "");
              branchSelect.appendChild(opt);
            });
          })
          .catch(function () {});
      });
    }
  });
})();
