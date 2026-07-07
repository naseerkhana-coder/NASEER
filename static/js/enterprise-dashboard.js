/**
 * Enterprise Dashboard (MODULE-008) — widget grid, drag-drop, resize, refresh.
 */
(function () {
  "use strict";

  var GRID_COLS = 12;
  var root = document.getElementById("enterprise-dashboard-root");
  if (!root) return;

  var gridEl = document.getElementById("enterprise-widget-grid");
  var loadingEl = document.getElementById("enterprise-dash-loading");
  var statusEl = document.getElementById("enterprise-dash-status");
  var canConfigure = root.getAttribute("data-can-configure") === "1";
  var canReset = root.getAttribute("data-can-reset") === "1";

  var state = {
    layout: null,
    widgets: {},
    drag: null,
    resize: null,
  };

  function setStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color = isError ? "var(--erp-danger, #f87171)" : "";
  }

  function fetchJson(url, options) {
    return fetch(url, Object.assign({ credentials: "same-origin", headers: { Accept: "application/json" } }, options || {}))
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (body) {
            throw new Error(body.error || ("HTTP " + res.status));
          });
        }
        return res.json();
      });
  }

  function colSpan(w) {
    return "span " + Math.max(1, Math.min(GRID_COLS, w || 4));
  }

  function rowSpan(h) {
    return "span " + Math.max(1, h || 2);
  }

  function renderWidgetShell(item, meta) {
    var el = document.createElement("article");
    el.className = "enterprise-widget";
    el.dataset.widgetKey = item.key;
    el.style.gridColumn = colSpan(item.w);
    el.style.gridRow = rowSpan(item.h);
    el.innerHTML =
      '<header class="enterprise-widget-header" draggable="' + (canConfigure ? "true" : "false") + '">' +
      '<h2 class="enterprise-widget-title">' + escapeHtml(meta.title || item.key) + "</h2>" +
      '<div class="enterprise-widget-actions">' +
      '<button type="button" class="enterprise-widget-refresh" title="Refresh" aria-label="Refresh widget"><i class="fa-solid fa-rotate"></i></button>' +
      (canConfigure ? '<button type="button" class="enterprise-widget-fav" title="Favorite" aria-label="Favorite"><i class="fa-regular fa-star"></i></button>' : "") +
      "</div></header>" +
      '<div class="enterprise-widget-body" id="widget-body-' + item.key + '"><span class="enterprise-widget-empty">Loading…</span></div>' +
      (canConfigure ? '<span class="enterprise-widget-resize" aria-hidden="true"></span>' : "");
    return el;
  }

  function escapeHtml(text) {
    var d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
  }

  function formatWidgetBody(key, data) {
    if (!data || data.empty) {
      return '<p class="enterprise-widget-empty">' + escapeHtml(data && data.message ? data.message : "No data") + "</p>";
    }
    if (key === "quick_actions" && data.actions) {
      return data.actions.map(function (a) {
        return '<a class="erp-btn erp-btn-ghost erp-btn-sm" href="/' + escapeHtml(a.endpoint) + '">' +
          '<i class="fa-solid ' + escapeHtml(a.icon || "fa-bolt") + '"></i> ' + escapeHtml(a.label) + "</a> ";
      }).join(" ");
    }
    if (key === "ai_insights") {
      var parts = [];
      if (data.daily_highlights) {
        parts.push("<strong>Highlights</strong><ul>" + data.daily_highlights.map(function (h) { return "<li>" + escapeHtml(h) + "</li>"; }).join("") + "</ul>");
      }
      if (data.risk_alerts) {
        parts.push("<strong>Risks</strong><ul>" + data.risk_alerts.map(function (h) { return "<li>" + escapeHtml(h) + "</li>"; }).join("") + "</ul>");
      }
      if (data.pending_task_suggestions) {
        parts.push("<strong>Suggestions</strong><ul>" + data.pending_task_suggestions.map(function (h) { return "<li>" + escapeHtml(h) + "</li>"; }).join("") + "</ul>");
      }
      return parts.join("") || escapeHtml(data.summary || "");
    }
    if (typeof data.count === "number" || typeof data.total_pending === "number") {
      var val = data.count != null ? data.count : data.total_pending;
      return '<div class="enterprise-widget-stat">' + val + "</div>";
    }
    if (typeof data.present === "number") {
      return '<div class="enterprise-widget-stat">' + data.present + '</div><div>Present today' +
        (typeof data.absent === "number" ? " · " + data.absent + " absent" : "") + "</div>";
    }
    if (typeof data.pending_count === "number") {
      return '<div class="enterprise-widget-stat">' + data.pending_count + "</div><div>Pending</div>";
    }
    if (data.summary && typeof data.summary === "object") {
      var s = data.summary;
      return "<div>Checker: " + (s.pending_checker || 0) + " · Approver: " + (s.pending_approval || 0) + "</div>";
    }
    if (data.items && data.items.length) {
      return "<ul>" + data.items.slice(0, 5).map(function (row) {
        var label = row.project_name || row.title || row.module_name || row.page_path || row.bill_no || ("#" + (row.id || ""));
        return "<li>" + escapeHtml(String(label)) + "</li>";
      }).join("") + "</ul>";
    }
    if (data.events && data.events.length) {
      return "<ul>" + data.events.map(function (ev) {
        return "<li>" + escapeHtml(ev.label || ev.type) + " — " + escapeHtml(ev.start || "") + "</li>";
      }).join("") + "</ul>";
    }
    if (data.actions) {
      return formatWidgetBody("quick_actions", data);
    }
    return "<pre style='white-space:pre-wrap;font-size:0.75rem;margin:0'>" + escapeHtml(JSON.stringify(data, null, 2).slice(0, 800)) + "</pre>";
  }

  function loadWidgetData(key) {
    var body = document.getElementById("widget-body-" + key);
    if (!body) return;
    body.innerHTML = '<span class="enterprise-widget-empty">Loading…</span>';
    fetchJson("/api/dashboard/widgets/" + encodeURIComponent(key) + "/data")
      .then(function (data) {
        body.innerHTML = formatWidgetBody(key, data);
      })
      .catch(function (err) {
        body.innerHTML = '<p class="enterprise-widget-empty">' + escapeHtml(err.message) + "</p>";
      });
  }

  function renderGrid() {
    if (!state.layout || !state.layout.widgets) return;
    gridEl.innerHTML = "";
    state.layout.widgets.forEach(function (item) {
      var meta = state.widgets[item.key] || { title: item.key };
      var el = renderWidgetShell(item, meta);
      gridEl.appendChild(el);
      var refreshBtn = el.querySelector(".enterprise-widget-refresh");
      if (refreshBtn) {
        refreshBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          loadWidgetData(item.key);
        });
      }
      if (canConfigure) {
        bindDrag(el, item);
        bindResize(el, item);
      }
      loadWidgetData(item.key);
    });
  }

  function getLayoutItems() {
    var items = [];
    gridEl.querySelectorAll(".enterprise-widget").forEach(function (el) {
      var key = el.dataset.widgetKey;
      var col = el.style.gridColumn || "";
      var row = el.style.gridRow || "";
      var w = parseInt(col.replace(/\D/g, ""), 10) || 4;
      var h = parseInt(row.replace(/\D/g, ""), 10) || 2;
      var match = state.layout.widgets.find(function (x) { return x.key === key; });
      items.push({
        key: key,
        x: match ? match.x : 0,
        y: match ? match.y : 0,
        w: w,
        h: h,
      });
    });
    return items;
  }

  function saveLayout() {
    if (!canConfigure) return;
    var payload = {
      layout: {
        version: 1,
        columns: GRID_COLS,
        widgets: getLayoutItems(),
      },
    };
    setStatus("Saving layout…");
    fetchJson("/api/dashboard/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function () {
        setStatus("Layout saved.");
        setTimeout(function () { setStatus(""); }, 2500);
      })
      .catch(function (err) {
        setStatus(err.message, true);
      });
  }

  function resetLayout() {
    if (!canReset) return;
    if (!window.confirm("Reset your dashboard layout to defaults?")) return;
    fetchJson("/api/dashboard/layout/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then(function (data) {
        if (data.layout) {
          state.layout = data.layout;
          renderGrid();
        } else {
          return init();
        }
        setStatus("Layout reset.");
      })
      .catch(function (err) {
        setStatus(err.message, true);
      });
  }

  function bindDrag(el, item) {
    var header = el.querySelector(".enterprise-widget-header");
    if (!header) return;
    header.addEventListener("dragstart", function (e) {
      state.drag = { el: el, item: item };
      el.classList.add("is-dragging");
      e.dataTransfer.effectAllowed = "move";
    });
    header.addEventListener("dragend", function () {
      el.classList.remove("is-dragging");
      state.drag = null;
    });
    el.addEventListener("dragover", function (e) {
      if (!state.drag || state.drag.el === el) return;
      e.preventDefault();
    });
    el.addEventListener("drop", function (e) {
      e.preventDefault();
      if (!state.drag || state.drag.el === el) return;
      var parent = gridEl;
      var nodes = Array.prototype.slice.call(parent.children);
      var fromIdx = nodes.indexOf(state.drag.el);
      var toIdx = nodes.indexOf(el);
      if (fromIdx < toIdx) {
        parent.insertBefore(state.drag.el, el.nextSibling);
      } else {
        parent.insertBefore(state.drag.el, el);
      }
    });
  }

  function bindResize(el, item) {
    var handle = el.querySelector(".enterprise-widget-resize");
    if (!handle) return;
    handle.addEventListener("mousedown", function (e) {
      e.preventDefault();
      e.stopPropagation();
      var startX = e.clientX;
      var startY = e.clientY;
      var startW = item.w || 4;
      var startH = item.h || 2;
      function onMove(ev) {
        var dx = ev.clientX - startX;
        var dy = ev.clientY - startY;
        var newW = Math.max(2, Math.min(GRID_COLS, startW + Math.round(dx / 80)));
        var newH = Math.max(1, startH + Math.round(dy / 60));
        item.w = newW;
        item.h = newH;
        el.style.gridColumn = colSpan(newW);
        el.style.gridRow = rowSpan(newH);
      }
      function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  function refreshAll() {
    if (!state.layout || !state.layout.widgets) return;
    state.layout.widgets.forEach(function (w) {
      loadWidgetData(w.key);
    });
    setStatus("Refreshed.");
    setTimeout(function () { setStatus(""); }, 2000);
  }

  function init() {
    return Promise.all([
      fetchJson("/api/dashboard/widgets"),
      fetchJson("/api/dashboard/layout"),
    ])
      .then(function (results) {
        var widgetResp = results[0];
        var layoutResp = results[1];
        (widgetResp.widgets || []).forEach(function (w) {
          state.widgets[w.key] = w;
        });
        state.layout = layoutResp.layout || { version: 1, columns: GRID_COLS, widgets: [] };
        if (loadingEl) loadingEl.remove();
        renderGrid();
      })
      .catch(function (err) {
        if (loadingEl) loadingEl.textContent = err.message;
        setStatus(err.message, true);
      });
  }

  var refreshBtn = document.getElementById("enterprise-dash-refresh");
  var saveBtn = document.getElementById("enterprise-dash-save");
  var resetBtn = document.getElementById("enterprise-dash-reset");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshAll);
  if (saveBtn) saveBtn.addEventListener("click", saveLayout);
  if (resetBtn) resetBtn.addEventListener("click", resetLayout);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
