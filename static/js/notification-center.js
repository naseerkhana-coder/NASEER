/**
 * Notification Center (MODULE-022)
 */
(function () {
  "use strict";

  var root = document.getElementById("notification-center-root");
  if (!root) return;

  var canEdit = root.getAttribute("data-can-edit") === "1";

  function fetchJson(url, options) {
    return fetch(url, Object.assign({
      credentials: "same-origin",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
    }, options || {})).then(function (res) {
      return res.json().then(function (body) {
        if (!res.ok) throw new Error(body.error || "Request failed");
        return body;
      });
    });
  }

  function escapeHtml(text) {
    var d = document.createElement("div");
    d.textContent = text == null ? "" : String(text);
    return d.innerHTML;
  }

  function loadDashboard() {
    return fetchJson("/api/v1/notifications/dashboard").then(function (data) {
      var m = data.metrics || {};
      document.getElementById("nc-total").textContent = m.total != null ? m.total : "0";
      document.getElementById("nc-unread").textContent = m.unread != null ? m.unread : "0";
      document.getElementById("nc-failed").textContent = m.failed != null ? m.failed : "0";
      document.getElementById("nc-high").textContent = m.high_priority != null ? m.high_priority : "0";
      var chEl = document.getElementById("nc-channels");
      chEl.innerHTML = "";
      var ch = m.delivery_by_channel || {};
      Object.keys(ch).forEach(function (key) {
        var row = document.createElement("div");
        row.className = "nc-channel-bar";
        row.innerHTML = "<span>" + escapeHtml(key) + "</span><span>" + ch[key] + "</span>";
        chEl.appendChild(row);
      });
      var trendEl = document.getElementById("nc-trend");
      if (m.trend && m.trend.length) {
        trendEl.textContent = "14-day trend: " + m.trend.map(function (t) {
          return t.date + " (" + t.count + ")";
        }).join(", ");
      } else {
        trendEl.textContent = "";
      }
    });
  }

  function loadList() {
    var unread = document.getElementById("nc-filter-unread").value;
    var qs = unread ? "?unread_only=1" : "";
    return fetchJson("/api/v1/notifications" + qs).then(function (data) {
      var tbody = document.getElementById("nc-tbody");
      tbody.innerHTML = "";
      var items = data.items || [];
      if (!items.length) {
        tbody.innerHTML = "<tr><td colspan=\"7\">No notifications.</td></tr>";
        return;
      }
      items.forEach(function (n) {
        var tr = document.createElement("tr");
        if (!n.is_read) tr.className = "nc-row-unread";
        tr.innerHTML =
          "<td>" + escapeHtml(n.created_at) + "</td>" +
          "<td>" + escapeHtml(n.title || n.message) + "</td>" +
          "<td>" + escapeHtml(n.notification_type) + "</td>" +
          "<td>" + escapeHtml(n.priority) + "</td>" +
          "<td>" + escapeHtml(n.channel) + "</td>" +
          "<td>" + escapeHtml(n.status) + "</td>" +
          "<td>" + (n.is_read ? "" : "<button type=\"button\" class=\"erp-btn erp-btn-ghost erp-btn-sm nc-read\" data-id=\"" + n.id + "\">Mark read</button>") + "</td>";
        tbody.appendChild(tr);
      });
      tbody.querySelectorAll(".nc-read").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-id");
          fetchJson("/api/v1/notifications/" + id + "/read", { method: "POST", body: "{}" })
            .then(refresh)
            .catch(function (e) { alert(e.message); });
        });
      });
    });
  }

  function loadPreferences() {
    if (!canEdit) return Promise.resolve();
    return fetchJson("/api/v1/notifications/preferences").then(function (data) {
      var p = data.preferences || {};
      var form = document.getElementById("nc-prefs-form");
      if (!form) return;
      form.in_app_enabled.checked = !!p.in_app_enabled;
      form.email_enabled.checked = !!p.email_enabled;
      form.sms_enabled.checked = !!p.sms_enabled;
      form.daily_summary.checked = !!p.daily_summary;
      form.weekly_summary.checked = !!p.weekly_summary;
      form.quiet_hours_start.value = p.quiet_hours_start || "";
      form.quiet_hours_end.value = p.quiet_hours_end || "";
    });
  }

  function refresh() {
    return Promise.all([loadDashboard(), loadList()]);
  }

  document.getElementById("nc-refresh").addEventListener("click", function () {
    refresh().catch(function (e) { alert(e.message); });
  });

  document.getElementById("nc-filter-unread").addEventListener("change", function () {
    loadList().catch(function (e) { alert(e.message); });
  });

  document.getElementById("nc-mark-all").addEventListener("click", function () {
    fetchJson("/api/v1/notifications/read-all", { method: "POST", body: "{}" })
      .then(refresh)
      .catch(function (e) { alert(e.message); });
  });

  document.getElementById("nc-prefs-toggle").addEventListener("click", function () {
    document.getElementById("nc-prefs-panel").classList.toggle("is-open");
  });

  var prefsForm = document.getElementById("nc-prefs-form");
  if (prefsForm && canEdit) {
    prefsForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var payload = {
        in_app_enabled: prefsForm.in_app_enabled.checked,
        email_enabled: prefsForm.email_enabled.checked,
        sms_enabled: prefsForm.sms_enabled.checked,
        daily_summary: prefsForm.daily_summary.checked,
        weekly_summary: prefsForm.weekly_summary.checked,
        quiet_hours_start: prefsForm.quiet_hours_start.value,
        quiet_hours_end: prefsForm.quiet_hours_end.value,
      };
      fetchJson("/api/v1/notifications/preferences", {
        method: "PUT",
        body: JSON.stringify(payload),
      }).then(function () {
        alert("Preferences saved.");
      }).catch(function (err) { alert(err.message); });
    });
  }

  loadPreferences().then(refresh).catch(function (e) {
    document.getElementById("nc-tbody").innerHTML = "<tr><td colspan=\"7\">" + escapeHtml(e.message) + "</td></tr>";
  });
})();
