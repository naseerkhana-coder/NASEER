(function () {
  "use strict";

  var modal = document.getElementById("ai-assistant-modal");
  var fab = document.getElementById("ai-assistant-fab");
  if (!modal || !fab) return;

  var state = {
    mode: "assistant",
    projectId: null,
    reportDate: null,
  };

  function qs(sel) {
    return modal.querySelector(sel);
  }

  function showStatus(text, isError) {
    var el = qs("[data-ai-status]");
    if (!el) return;
    if (!text) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.hidden = false;
    el.textContent = text;
    el.classList.toggle("ai-assistant-status--error", !!isError);
  }

  function showOutput(title, body) {
    var wrap = qs("[data-ai-output]");
    var titleEl = qs("[data-ai-output-title]");
    var bodyEl = qs("[data-ai-output-body]");
    if (!wrap || !titleEl || !bodyEl) return;
    titleEl.textContent = title || "Result";
    bodyEl.textContent = body || "";
    wrap.hidden = !body;
  }

  function parseJsonInput(raw) {
    var text = (raw || "").trim();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch (e) {
      throw new Error("Invalid JSON in measurements field.");
    }
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload || {}),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var msg = (data && data.error) || res.statusText || "Request failed";
          var err = new Error(msg);
          err.status = res.status;
          err.code = data && data.code;
          throw err;
        }
        return data;
      });
    });
  }

  function setTab(name) {
    state.mode = name;
    modal.querySelectorAll("[data-ai-tab]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-ai-tab") === name);
    });
    modal.querySelectorAll("[data-ai-panel]").forEach(function (panel) {
      var active = panel.getAttribute("data-ai-panel") === name;
      panel.hidden = !active;
    });
  }

  function openPanel(opts) {
    opts = opts || {};
    state.projectId = opts.projectId != null ? opts.projectId : state.projectId;
    state.reportDate = opts.reportDate != null ? opts.reportDate : state.reportDate;
    if (opts.mode) setTab(opts.mode);
    var subtitle = qs("[data-ai-assistant-subtitle]");
    if (subtitle) {
      var parts = [];
      if (state.projectId) parts.push("Project #" + state.projectId);
      if (state.reportDate) parts.push("Date " + state.reportDate);
      subtitle.textContent = parts.length
        ? parts.join(" · ") + " — AI uses your ERP session data."
        : "Ask about projects, BOQ, DPR, or documents.";
    }
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    showStatus("");
    showOutput("", "");
  }

  function closePanel() {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    showStatus("");
  }

  function detectContextFromPage() {
    var projectSelect =
      document.querySelector("[data-boq-project-select]") ||
      document.querySelector("[data-dpr-form] [name='project_id']") ||
      document.querySelector("select[name='project_id']");
    if (projectSelect && projectSelect.value) {
      state.projectId = parseInt(projectSelect.value, 10) || null;
    }
    var dateInput =
      document.querySelector("[data-dpr-form] [name='report_date']") ||
      document.querySelector("input[name='report_date']");
    if (dateInput && dateInput.value) {
      state.reportDate = dateInput.value;
    }
  }

  fab.hidden = false;
  fab.setAttribute("aria-hidden", "false");
  detectContextFromPage();

  document.querySelectorAll("[data-ai-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      detectContextFromPage();
      openPanel({
        mode: btn.getAttribute("data-ai-mode") || "assistant",
        projectId: btn.getAttribute("data-ai-project-id") || state.projectId,
      });
    });
  });

  fab.querySelector("[data-ai-assistant-open]").addEventListener("click", function () {
    detectContextFromPage();
    openPanel({ mode: "assistant" });
  });

  modal.querySelectorAll("[data-ai-assistant-close]").forEach(function (el) {
    el.addEventListener("click", closePanel);
  });

  modal.querySelectorAll("[data-ai-tab]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setTab(btn.getAttribute("data-ai-tab"));
    });
  });

  qs("[data-ai-assistant-send]").addEventListener("click", function () {
    var message = (qs("[data-ai-assistant-message]").value || "").trim();
    if (!message) {
      showStatus("Enter a message.", true);
      return;
    }
    showStatus("Thinking…");
    postJson("/api/ai/project-assistant", {
      message: message,
      project_id: state.projectId,
    })
      .then(function (data) {
        showStatus("");
        showOutput("Assistant", data.reply || "");
      })
      .catch(function (err) {
        showStatus(err.message, true);
      });
  });

  qs("[data-ai-dpr-generate]").addEventListener("click", function () {
    var notes = (qs("[data-ai-dpr-notes]").value || "").trim();
    var measurements = null;
    try {
      measurements = parseJsonInput(qs("[data-ai-dpr-measurements]").value);
    } catch (e) {
      showStatus(e.message, true);
      return;
    }
    showStatus("Generating DPR narrative…");
    postJson("/api/ai/dpr-writer", {
      project_id: state.projectId,
      date: state.reportDate,
      notes: notes,
      measurements: measurements,
    })
      .then(function (data) {
        showStatus("");
        showOutput("Suggested DPR narrative", data.narrative || "");
        var workDesc = document.querySelector("[data-dpr-form] [name='work_description']");
        if (workDesc && data.narrative && !workDesc.value.trim()) {
          workDesc.value = data.narrative;
        }
      })
      .catch(function (err) {
        showStatus(err.message, true);
      });
  });

  qs("[data-ai-boq-search]").addEventListener("click", function () {
    var query = (qs("[data-ai-boq-query]").value || "").trim();
    if (!query) {
      showStatus("Enter a search query.", true);
      return;
    }
    showStatus("Searching BOQ…");
    postJson("/api/ai/boq-search", { query: query, project_id: state.projectId })
      .then(function (data) {
        showStatus("");
        var lines = [data.explanation || ""];
        (data.items || []).forEach(function (item) {
          lines.push(
            "- #" + item.id + " " + (item.boq_number || "") + " " +
            (item.item_description || "") + " (" + item.quantity + " " + (item.unit || "") + ")"
          );
        });
        if (!(data.items || []).length) {
          lines.push("(No matching BOQ items returned.)");
        }
        showOutput("BOQ search", lines.join("\n"));
      })
      .catch(function (err) {
        showStatus(err.message, true);
      });
  });

  qs("[data-ai-doc-summarize]").addEventListener("click", function () {
    var text = (qs("[data-ai-doc-text]").value || "").trim();
    if (!text) {
      showStatus("Paste document text to summarize.", true);
      return;
    }
    showStatus("Summarizing…");
    postJson("/api/ai/document-reader", { text: text, project_id: state.projectId })
      .then(function (data) {
        showStatus("");
        var lines = [data.summary || ""];
        (data.key_points || []).forEach(function (point) {
          lines.push("• " + point);
        });
        if ((data.action_items || []).length) {
          lines.push("\nAction items:");
          data.action_items.forEach(function (item) {
            lines.push("- " + item);
          });
        }
        showOutput("Document summary", lines.join("\n"));
      })
      .catch(function (err) {
        showStatus(err.message, true);
      });
  });

  window.MaxekAI = {
    open: openPanel,
    close: closePanel,
  };
})();
