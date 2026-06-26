(function () {
  function parseJson(res) {
    return res.json();
  }

  function initPurchaseRequestForm() {
    var select = document.getElementById("pr_material_request_id");
    if (!select) return;
    select.addEventListener("change", function () {
      var id = select.value;
      if (!id) return;
      fetch("/api/purchase-request/" + encodeURIComponent(id))
        .then(parseJson)
        .then(function (data) {
          if (data.error) return;
          var set = function (name, val) {
            var el = document.querySelector('[name="' + name + '"]');
            if (el) el.value = val != null ? val : "";
          };
          set("project_id", data.project_id);
          set("request_date", data.request_date || new Date().toISOString().slice(0, 10));
          set("item_description", data.item_name || data.mr_item_name || data.item_description);
          set("quantity", data.quantity);
          set("unit", data.unit);
          set("material_id", data.material_id);
        })
        .catch(function () {});
    });
    if (select.value) select.dispatchEvent(new Event("change"));
  }

  function initPurchaseOrderForm() {
    var prSelect = document.getElementById("po_purchase_request_id");
    if (!prSelect) return;
    prSelect.addEventListener("change", function () {
      var id = prSelect.value;
      if (!id) return;
      fetch("/api/purchase-request/" + encodeURIComponent(id))
        .then(parseJson)
        .then(function (data) {
          if (data.error) return;
          var set = function (name, val) {
            var el = document.querySelector('[name="' + name + '"]');
            if (el) el.value = val != null ? val : "";
          };
          set("project_id", data.project_id);
          var tbody = document.querySelector("[data-lines-table] tbody");
          if (!tbody) return;
          var row = tbody.querySelector("[data-line-row]");
          if (!row) return;
          var matSelect = row.querySelector('select[name="material_id[]"]');
          if (matSelect && data.material_id) matSelect.value = String(data.material_id);
          var desc = row.querySelector('input[name="description[]"]');
          if (desc) desc.value = data.item_description || data.item_name || "";
          var qty = row.querySelector('input[name="quantity[]"]');
          if (qty) qty.value = data.quantity || 1;
          var unit = row.querySelector('input[name="unit[]"]');
          if (unit) unit.value = data.unit || "Nos";
        })
        .catch(function () {});
    });
    if (prSelect.value) prSelect.dispatchEvent(new Event("change"));
  }

  function renderGrnBalancePanel(lines) {
    var panel = document.getElementById("grn-balance-panel");
    var tbody = document.getElementById("grn-balance-rows");
    if (!panel || !tbody) return;
    tbody.innerHTML = "";
    if (!lines || !lines.length) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    lines.forEach(function (line) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + (line.material_code || "—") + "</td>" +
        "<td>" + (line.description || "—") + "</td>" +
        "<td class=\"num\">" + (line.ordered_qty || 0) + "</td>" +
        "<td class=\"num\">" + (line.previously_received || 0) + "</td>" +
        "<td class=\"num\">" + (line.balance_qty || 0) + "</td>";
      tbody.appendChild(tr);
    });
  }

  function initGrnPoBalance() {
    var poSelect = document.querySelector('select[name="purchase_order_id"]');
    if (!poSelect) return;
    var loadBalance = function () {
      var poId = poSelect.value;
      if (!poId) {
        renderGrnBalancePanel([]);
        return;
      }
      fetch("/api/purchase-order/" + encodeURIComponent(poId) + "/grn-balance")
        .then(parseJson)
        .then(function (data) {
          renderGrnBalancePanel(data.lines || []);
        })
        .catch(function () {});
    };
    poSelect.addEventListener("change", loadBalance);
    loadBalance();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initPurchaseRequestForm();
    initPurchaseOrderForm();
    initGrnPoBalance();
  });
})();
