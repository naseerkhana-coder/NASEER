(function () {
  function bindLineTable(root) {
    if (!root) return;
    var table = root.querySelector('[data-lines-table]');
    if (!table) return;
    var tbody = table.querySelector('tbody');

    function insertRow(clone) {
      if (window.MaxekSpreadsheetGrid && window.MaxekSpreadsheetGrid.insertRowAfterCurrent) {
        window.MaxekSpreadsheetGrid.insertRowAfterCurrent(table, clone);
      } else {
        tbody.appendChild(clone);
        if (window.MaxekDataEntry && window.MaxekDataEntry.focusFirstField) {
          window.MaxekDataEntry.focusFirstField(clone);
        }
      }
      table.dispatchEvent(new CustomEvent('maxek:row-added', { bubbles: true, detail: { row: clone } }));
    }

    root.addEventListener('click', function (e) {
      var addBtn = e.target.closest('[data-add-line]');
      if (addBtn) {
        e.preventDefault();
        var first = tbody.querySelector('[data-line-row]');
        if (!first) return;
        var clone = first.cloneNode(true);
        clone.querySelectorAll('input').forEach(function (inp) {
          if (inp.type === 'number') inp.value = inp.name.indexOf('quantity') >= 0 ? '1' : '0';
          else inp.value = '';
        });
        clone.querySelectorAll('select').forEach(function (sel) { sel.selectedIndex = 0; });
        insertRow(clone);
        if (window.MaxekSpreadsheetGrid) window.MaxekSpreadsheetGrid.markDirty(table);
      }
      var rmBtn = e.target.closest('[data-remove-line]');
      if (rmBtn) {
        e.preventDefault();
        var rows = tbody.querySelectorAll('[data-line-row]');
        if (rows.length <= 1) return;
        if (window.MaxekSpreadsheetGrid) window.MaxekSpreadsheetGrid.saveScrollPosition(table);
        rmBtn.closest('[data-line-row]').remove();
        if (window.MaxekSpreadsheetGrid) {
          window.MaxekSpreadsheetGrid.restoreScrollPosition(table);
          window.MaxekSpreadsheetGrid.markDirty(table);
        }
      }
    });
    table.addEventListener('change', function (e) {
      var sel = e.target.closest('select[name="material_id[]"]');
      if (!sel) return;
      var opt = sel.options[sel.selectedIndex];
      var row = sel.closest('[data-line-row]');
      if (!row || !opt) return;
      var unit = row.querySelector('input[name="unit[]"]');
      var desc = row.querySelector('input[name="description[]"]');
      if (unit && opt.getAttribute('data-unit')) unit.value = opt.getAttribute('data-unit');
      if (desc && !desc.value && opt.text) desc.value = opt.text.split('—').pop().trim();
      var gstSel = row.querySelector('select[name="gst_percent[]"]');
      if (gstSel && opt.getAttribute('data-gst')) gstSel.value = opt.getAttribute('data-gst');
    });
  }
  document.querySelectorAll('[data-store-lines-form]').forEach(bindLineTable);
})();
