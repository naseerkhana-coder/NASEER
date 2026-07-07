(function () {
  "use strict";

  function showModal(modal, show) {
    if (!modal) return;
    modal.hidden = !show;
    modal.style.display = show ? "flex" : "none";
  }

  function switchTab(tabName) {
    document.querySelectorAll(".erp-tab-panel").forEach(function (panel) {
      panel.hidden = panel.id !== "tab-" + tabName;
    });
    document.querySelectorAll(".erp-tab").forEach(function (tab) {
      tab.classList.toggle("active", tab.getAttribute("data-tab") === tabName);
    });
    if (tabName === "history") loadHistory();
    if (tabName === "ai") loadInsights();
  }

  function renderQueue(items) {
    var tbody = document.getElementById("queue-tbody");
    if (!tbody) return;
    if (!items || !items.length) {
      tbody.innerHTML = "<tr><td colspan=\"6\">No items in this queue.</td></tr>";
      return;
    }
    tbody.innerHTML = items
      .map(function (item) {
        var aid = item.id || item.approval_id;
        return (
          "<tr>" +
          "<td>" + (item.reference_no || "—") + "</td>" +
          "<td>" + (item.module_name || item.module_id || "—") + "</td>" +
          "<td>" + (item.created_by || item.maker_name || "—") + "</td>" +
          "<td>" + (item.status_label || item.workflow_status || "—") + "</td>" +
          "<td>" + ((item.created_at || "").substring(0, 16) || "—") + "</td>" +
          "<td>" +
          (aid
            ? "<button type=\"button\" class=\"erp-btn erp-btn-sm erp-btn-primary js-approve\" data-id=\"" +
              aid +
              "\">Act</button>"
            : "—") +
          "</td></tr>"
        );
      })
      .join("");
  }

  function loadQueue(queue) {
    fetch("/api/workflow-engine/queue/" + encodeURIComponent(queue), { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        renderQueue(data.items || []);
      })
      .catch(function () {
        renderQueue([]);
      });
  }

  function loadHistory() {
    var tbody = document.getElementById("history-tbody");
    if (!tbody) return;
    fetch("/api/workflow-engine/history?limit=50", { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        var items = data.items || [];
        if (!items.length) {
          tbody.innerHTML = "<tr><td colspan=\"5\">No history found.</td></tr>";
          return;
        }
        tbody.innerHTML = items
          .map(function (item) {
            var tl = (item.history && item.history.timeline) || [];
            var tlText = tl
              .slice(0, 3)
              .map(function (e) {
                return e.event + " (" + e.user + ")";
              })
              .join(" → ");
            return (
              "<tr>" +
              "<td>" +
              (item.module_id || "").toUpperCase().substring(0, 6) +
              "-" +
              (item.record_id || "") +
              "</td>" +
              "<td>" +
              (item.module_name || item.module_id || "—") +
              "</td>" +
              "<td>" +
              (item.status_label || "—") +
              "</td>" +
              "<td>" +
              ((item.created_at || "").substring(0, 16) || "—") +
              "</td>" +
              "<td><small>" +
              (tlText || "—") +
              "</small></td></tr>"
            );
          })
          .join("");
      });
  }

  function loadInsights() {
    var el = document.getElementById("wf-ai-content");
    if (!el) return;
    fetch("/api/workflow-engine/ai/insights", { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        var recs = (data.recommendations || []).map(function (r) {
          return "<li>" + r + "</li>";
        }).join("");
        el.innerHTML =
          "<p><strong>Delay risk:</strong> " +
          (data.delay_risk || "—") +
          " &nbsp; <strong>Stuck approvals:</strong> " +
          (data.stuck_approvals || 0) +
          "</p>" +
          (recs ? "<ul>" + recs + "</ul>" : "") +
          "<pre style=\"font-size:0.8rem;overflow:auto;\">" +
          JSON.stringify(data.workload_by_module || [], null, 2) +
          "</pre>";
      })
      .catch(function () {
        el.textContent = "Insights unavailable.";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".erp-tab[data-tab]").forEach(function (tab) {
      tab.addEventListener("click", function (e) {
        e.preventDefault();
        switchTab(tab.getAttribute("data-tab"));
      });
    });

    document.querySelectorAll(".js-load-queue").forEach(function (btn) {
      btn.addEventListener("click", function () {
        loadQueue(btn.getAttribute("data-queue"));
      });
    });

    document.getElementById("queue-tbody") &&
      document.getElementById("queue-tbody").addEventListener("click", function (e) {
        var btn = e.target.closest(".js-approve");
        if (!btn) return;
        var id = btn.getAttribute("data-id");
        var comments = window.prompt("Comments (optional):") || "";
        fetch("/api/workflow-engine/approval/" + id + "/action", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "verify", comments: comments }),
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            alert(data.message || data.error || "Done");
            loadQueue("checker");
          });
      });

    var escBtn = document.getElementById("wf-run-escalations");
    if (escBtn) {
      escBtn.addEventListener("click", function () {
        var status = document.getElementById("wf-escalation-status");
        if (status) status.textContent = "Running…";
        fetch("/api/workflow-engine/escalations/run", {
          method: "POST",
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (status) status.textContent = "Sent " + (data.escalations_sent || 0) + " reminders.";
          });
      });
    }

    var importBtn = document.getElementById("workflow-import-btn");
    var importModal = document.getElementById("workflow-import-modal");
    var importClose = document.getElementById("workflow-import-close");
    var importRun = document.getElementById("workflow-import-run");
    var importFile = document.getElementById("workflow-import-file");
    var importStatus = document.getElementById("workflow-import-status");

    if (importBtn) {
      importBtn.addEventListener("click", function () {
        showModal(importModal, true);
      });
    }
    if (importClose) {
      importClose.addEventListener("click", function () {
        showModal(importModal, false);
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
        fetch("/api/workflow-engine/import/save", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (importStatus) {
              importStatus.textContent = data.ok
                ? "Imported " + (data.imported || 0) + ", updated " + (data.updated || 0)
                : data.error || "Import failed";
            }
            if (data.ok) window.location.reload();
          });
      });
    }
  });
})();
