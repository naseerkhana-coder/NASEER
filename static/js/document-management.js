(function () {
  "use strict";

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error((j && j.error) || "Request failed");
        return j;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var app = document.getElementById("document-management-app");
    if (!app) return;

    var uploadTrigger = document.getElementById("dms-upload-trigger");
    var uploadPanel = document.getElementById("dms-upload-panel");
    var uploadCancel = document.getElementById("dms-upload-cancel");
    var uploadForm = document.getElementById("dms-upload-form");
    var uploadStatus = document.getElementById("dms-upload-status");
    var dropzone = document.getElementById("dms-dropzone");
    var fileInput = document.getElementById("dms-file-input");
    var advToggle = document.getElementById("dms-toggle-advanced");
    var advPanel = document.getElementById("dms-advanced-search");
    var previewModal = document.getElementById("dms-preview-modal");
    var previewContent = document.getElementById("dms-preview-content");
    var previewClose = document.getElementById("dms-preview-close");

    function openPanel(panel) {
      if (panel) panel.classList.add("is-open");
    }
    function closePanel(panel) {
      if (panel) panel.classList.remove("is-open");
    }

    if (uploadTrigger) {
      uploadTrigger.addEventListener("click", function () {
        openPanel(uploadPanel);
        uploadPanel && uploadPanel.scrollIntoView({ behavior: "smooth" });
      });
    }
    if (uploadCancel) {
      uploadCancel.addEventListener("click", function () {
        closePanel(uploadPanel);
      });
    }
    if (advToggle && advPanel) {
      advToggle.addEventListener("click", function () {
        advPanel.classList.toggle("is-open");
      });
    }

    if (dropzone && fileInput) {
      dropzone.addEventListener("click", function () {
        fileInput.click();
      });
      dropzone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropzone.classList.add("is-dragover");
      });
      dropzone.addEventListener("dragleave", function () {
        dropzone.classList.remove("is-dragover");
      });
      dropzone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropzone.classList.remove("is-dragover");
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          fileInput.files = e.dataTransfer.files;
        }
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener("submit", function (e) {
        e.preventDefault();
        if (uploadStatus) uploadStatus.textContent = "Uploading…";
        var fd = new FormData(uploadForm);
        fetch("/api/document-management/upload", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json().then(function (j) {
              if (!r.ok) throw new Error((j && j.error) || "Upload failed");
              return j;
            });
          })
          .then(function () {
            if (uploadStatus) uploadStatus.textContent = "Upload complete. Reloading…";
            window.location.reload();
          })
          .catch(function (err) {
            if (uploadStatus) uploadStatus.textContent = err.message || "Upload failed";
          });
      });
    }

    document.querySelectorAll(".dms-preview-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        if (!id || !previewModal || !previewContent) return;
        previewContent.innerHTML = '<iframe src="/api/document-management/' + id + '/preview" style="width:100%;height:70vh;border:0;"></iframe>';
        previewModal.classList.add("is-open");
        previewModal.hidden = false;
      });
    });

    if (previewClose && previewModal) {
      previewClose.addEventListener("click", function () {
        previewModal.classList.remove("is-open");
        previewModal.hidden = true;
        if (previewContent) previewContent.innerHTML = "";
      });
    }

    document.querySelectorAll(".dms-rollback-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        var version = btn.getAttribute("data-version");
        if (!confirm("Rollback to version " + version + "?")) return;
        postJson("/api/document-management/" + id + "/rollback", { version_number: parseInt(version, 10) })
          .then(function () {
            window.location.reload();
          })
          .catch(function (err) {
            alert(err.message);
          });
      });
    });

    document.querySelectorAll(".dms-approve-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        postJson("/api/document-management/" + id + "/approve", {})
          .then(function () {
            window.location.reload();
          })
          .catch(function (err) {
            alert(err.message);
          });
      });
    });

    document.querySelectorAll(".dms-reject-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        var remarks = prompt("Rejection remarks (optional):") || "";
        postJson("/api/document-management/" + id + "/reject", { remarks: remarks })
          .then(function () {
            window.location.reload();
          })
          .catch(function (err) {
            alert(err.message);
          });
      });
    });

    var newFolderBtn = document.getElementById("dms-new-folder-btn");
    if (newFolderBtn) {
      newFolderBtn.addEventListener("click", function () {
        var name = prompt("New folder name:");
        if (!name) return;
        postJson("/api/document-management/folders", { folder_name: name })
          .then(function () {
            window.location.reload();
          })
          .catch(function (err) {
            alert(err.message);
          });
      });
    }
  });
})();
