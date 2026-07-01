(function () {
  'use strict';

  var DRAFT_INTERVAL_MS = 15000;
  var VIRTUAL_THRESHOLD = 100;
  var SCROLL_KEY_PREFIX = 'maxek-grid-scroll:';
  var DRAFT_KEY_PREFIX = 'maxek-grid-draft:';

  var grids = new WeakMap();

  function parseNum(value) {
    var n = parseFloat(value);
    return Number.isFinite(n) ? n : 0;
  }

  function isEditable(el) {
    if (!el || el.readOnly || el.disabled) return false;
    if (el.type === 'hidden') return false;
    if (el.tabIndex < 0) return false;
    if (el.offsetParent === null || el.closest('[hidden]')) return false;
    return el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA';
  }

  function isNumericInput(el) {
    if (!el) return false;
    if (el.type === 'number') return true;
    if (el.type === 'text' && el.getAttribute('inputmode') === 'decimal') return true;
    if (el.hasAttribute('data-numeric-input')) return true;
    if (el.classList && el.classList.contains('erp-field-numeric')) return true;
    return false;
  }

  function tableFocusables(table) {
    return Array.prototype.slice.call(
      table.querySelectorAll(
        'tbody input:not([type="hidden"]):not([readonly]):not([disabled]), '
        + 'tbody select:not([disabled]), '
        + 'tbody textarea:not([readonly]):not([disabled])'
      )
    ).filter(function (el) {
      return el.offsetParent !== null && !el.closest('[hidden]') && el.tabIndex !== -1;
    });
  }

  function cellPosition(input) {
    var cell = input.closest('td, th');
    var row = input.closest('tr');
    if (!cell || !row || !row.parentElement) return null;
    return {
      rowIndex: Array.prototype.indexOf.call(row.parentElement.children, row),
      cellIndex: Array.prototype.indexOf.call(row.children, cell),
      row: row,
      cell: cell,
      table: input.closest('table'),
    };
  }

  function focusTableAt(table, rowIndex, cellIndex) {
    if (!table) return null;
    var body = table.tBodies[0];
    if (!body) return null;
    var row = body.rows[rowIndex];
    if (!row || row.hidden) return null;
    var cell = row.cells[cellIndex];
    if (!cell) return null;
    var target = cell.querySelector(
      'input:not([type="hidden"]):not([readonly]):not([disabled]), '
      + 'select:not([disabled]), textarea:not([readonly]):not([disabled])'
    );
    if (!target || target.tabIndex === -1) return null;
    target.focus();
    if (isNumericInput(target) && typeof target.select === 'function') {
      try { target.select(); } catch (err) { /* ignore */ }
    }
    highlightActiveCell(target);
    return target;
  }

  function highlightActiveCell(el) {
    var table = el && el.closest('table');
    if (!table) return;
    table.querySelectorAll('.erp-spreadsheet-cell--active').forEach(function (td) {
      td.classList.remove('erp-spreadsheet-cell--active');
    });
    var cell = el.closest('td, th');
    if (cell) cell.classList.add('erp-spreadsheet-cell--active');
  }

  function moveFocus(input, direction) {
    var pos = cellPosition(input);
    if (!pos) return false;
    var table = pos.table;
    var body = table.tBodies[0];
    if (!body) return false;

    if (direction === 'right' || direction === 'left') {
      var colDelta = direction === 'right' ? 1 : -1;
      var col = pos.cellIndex + colDelta;
      while (col >= 0 && col < pos.row.cells.length) {
        if (focusTableAt(table, pos.rowIndex, col)) return true;
        col += colDelta;
      }
      if (direction === 'right') {
        var nextRow = pos.rowIndex + 1;
        while (nextRow < body.rows.length) {
          if (focusTableAt(table, nextRow, 0)) return true;
          nextRow += 1;
        }
      } else {
        var prevRow = pos.rowIndex - 1;
        while (prevRow >= 0) {
          var lastCol = body.rows[prevRow].cells.length - 1;
          while (lastCol >= 0) {
            if (focusTableAt(table, prevRow, lastCol)) return true;
            lastCol -= 1;
          }
          prevRow -= 1;
        }
      }
      return false;
    }

    if (direction === 'down' || direction === 'up') {
      var rowDelta = direction === 'down' ? 1 : -1;
      var nextR = pos.rowIndex + rowDelta;
      while (nextR >= 0 && nextR < body.rows.length) {
        if (focusTableAt(table, nextR, pos.cellIndex)) return true;
        nextR += rowDelta;
      }
      return false;
    }

    if (direction === 'next-row') {
      return moveFocus(input, 'down');
    }

    return false;
  }

  function shouldMoveHorizontal(input, direction) {
    if (input.tagName !== 'INPUT' && input.tagName !== 'TEXTAREA') return true;
    if (input.type === 'number' || input.type === 'date' || input.type === 'time') return true;
    var len = String(input.value || '').length;
    var start = input.selectionStart;
    var end = input.selectionEnd;
    if (start === null || end === null) return true;
    if (direction === 'left') return start === 0 && end === 0;
    if (direction === 'right') return start === len && end === len;
    return false;
  }

  function gridScrollKey(grid) {
    var form = grid.form;
    var id = grid.table.id || grid.table.getAttribute('data-spreadsheet-id');
    if (!id && form) {
      id = form.id || form.getAttribute('action') || 'form';
    }
    return SCROLL_KEY_PREFIX + window.location.pathname + ':' + (id || 'grid');
  }

  function draftKey(form) {
    var id = form.id || form.getAttribute('action') || window.location.pathname;
    return DRAFT_KEY_PREFIX + window.location.pathname + window.location.hash + ':' + id;
  }

  function saveScrollPosition(grid) {
    try {
      sessionStorage.setItem(gridScrollKey(grid), JSON.stringify({
        top: grid.scrollEl.scrollTop,
        left: grid.scrollEl.scrollLeft,
      }));
    } catch (err) { /* ignore */ }
  }

  function restoreScrollPosition(grid) {
    try {
      var raw = sessionStorage.getItem(gridScrollKey(grid));
      if (!raw) return;
      var data = JSON.parse(raw);
      if (data && typeof data.top === 'number') {
        grid.scrollEl.scrollTop = data.top;
        grid.scrollEl.scrollLeft = data.left || 0;
      }
    } catch (err) { /* ignore */ }
  }

  function serializeForm(form) {
    var fd = new FormData(form);
    var obj = {};
    fd.forEach(function (value, key) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        if (!Array.isArray(obj[key])) obj[key] = [obj[key]];
        obj[key].push(value);
      } else {
        obj[key] = value;
      }
    });
    return JSON.stringify({ ts: Date.now(), data: obj });
  }

  function escapeFieldName(name) {
    if (typeof CSS !== 'undefined' && CSS.escape) return CSS.escape(name);
    return String(name).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function applyDraft(form, payload) {
    if (!payload || !payload.data) return;
    Object.keys(payload.data).forEach(function (key) {
      var val = payload.data[key];
      var fields = form.querySelectorAll('[name="' + escapeFieldName(key) + '"]');
      if (!fields.length) return;
      if (Array.isArray(val)) {
        fields.forEach(function (field, idx) {
          if (idx < val.length) setFieldValue(field, val[idx]);
        });
      } else if (fields.length === 1) {
        setFieldValue(fields[0], val);
      }
    });
    form.dispatchEvent(new CustomEvent('maxek:draft-restored', { bubbles: true }));
  }

  function setFieldValue(field, value) {
    if (field.type === 'checkbox') {
      field.checked = value === 'on' || value === true || value === 'true' || value === '1';
    } else if (field.type === 'radio') {
      field.checked = String(field.value) === String(value);
    } else {
      field.value = value;
      field.classList.toggle('has-value', String(value || '').trim() !== '');
      field.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function markRowDirty(row) {
    if (row) row.setAttribute('data-spreadsheet-row--dirty', '');
  }

  function wrapTable(table) {
    if (table.closest('.erp-spreadsheet-grid')) return null;

    var parent = table.parentElement;
    var wrapper;
    var scroll = document.createElement('div');
    scroll.className = 'erp-spreadsheet-grid__scroll';

    if (parent && parent.classList.contains('erp-table-scroll')) {
      parent.classList.remove('erp-table-scroll');
      parent.classList.add('erp-spreadsheet-grid', 'erp-spreadsheet-grid--sticky-col');
      parent.insertBefore(scroll, table);
      scroll.appendChild(table);
      wrapper = parent;
    } else if (parent && parent.classList.contains('erp-spreadsheet-grid__scroll')) {
      wrapper = parent.parentElement;
      scroll = parent;
    } else {
      wrapper = document.createElement('div');
      wrapper.className = 'erp-spreadsheet-grid erp-spreadsheet-grid--sticky-col';
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(scroll);
      scroll.appendChild(table);
    }

    table.setAttribute('data-spreadsheet-grid', '');
    return { wrapper: wrapper, scroll: scroll, table: table };
  }

  function tagRows(table) {
    var body = table.tBodies[0];
    if (!body) return 0;
    var count = 0;
    Array.prototype.forEach.call(body.rows, function (row) {
      if (row.hasAttribute('data-spreadsheet-row-template') || row.hidden) return;
      row.setAttribute('data-spreadsheet-row', '');
      count += 1;
    });
    return count;
  }

  function bindKeyboard(grid) {
    grid.table.addEventListener('focusin', function (event) {
      if (isEditable(event.target)) highlightActiveCell(event.target);
    });

    document.addEventListener('keydown', function (event) {
      var el = event.target;
      if (!el || !grid.table.contains(el)) return;
      if (!isEditable(el)) return;

      if (event.key === 'Tab') {
        event.preventDefault();
        moveFocus(el, event.shiftKey ? 'left' : 'right');
        return;
      }

      if (event.key === 'Enter' && !event.shiftKey) {
        if (el.tagName === 'TEXTAREA') return;
        if (el.tagName === 'SELECT') return;
        if (moveFocus(el, 'next-row')) event.preventDefault();
        return;
      }

      if (event.key === 'ArrowDown') {
        if (moveFocus(el, 'down')) event.preventDefault();
        return;
      }

      if (event.key === 'ArrowUp') {
        if (moveFocus(el, 'up')) event.preventDefault();
        return;
      }

      if (event.key === 'ArrowRight' && shouldMoveHorizontal(el, 'right')) {
        if (moveFocus(el, 'right')) event.preventDefault();
        return;
      }

      if (event.key === 'ArrowLeft' && shouldMoveHorizontal(el, 'left')) {
        if (moveFocus(el, 'left')) event.preventDefault();
      }
    }, true);
  }

  function bindScrollPreserve(grid) {
    var timer = null;
    grid.scrollEl.addEventListener('scroll', function () {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        saveScrollPosition(grid);
      }, 100);
    }, { passive: true });
  }

  function bindDirtyTracking(grid) {
    var form = grid.form;
    if (!form) return;

    form.addEventListener('input', function (event) {
      if (!grid.table.contains(event.target)) return;
      grid.dirty = true;
      updateDraftBar(grid);
      var row = event.target.closest('tr');
      markRowDirty(row);
    }, true);

    form.addEventListener('change', function (event) {
      if (!grid.table.contains(event.target)) return;
      grid.dirty = true;
      updateDraftBar(grid);
      var row = event.target.closest('tr');
      markRowDirty(row);
    }, true);
  }

  function updateDraftBar(grid) {
    if (!grid.draftBar) return;
    grid.draftBar.classList.toggle('erp-spreadsheet-draft-bar--dirty', grid.dirty);
    if (grid.dirty) {
      grid.draftBar.textContent = 'Unsaved changes';
    }
  }

  function bindDraftAutoSave(grid) {
    var form = grid.form;
    if (!form || form.hasAttribute('data-spreadsheet-no-draft')) return;

    var key = draftKey(form);
    var savedRaw = null;
    try { savedRaw = localStorage.getItem(key); } catch (err) { /* ignore */ }

    if (savedRaw && !form.hasAttribute('data-spreadsheet-draft-applied')) {
      try {
        var saved = JSON.parse(savedRaw);
        if (saved && saved.ts && Date.now() - saved.ts < 7 * 24 * 60 * 60 * 1000) {
          var restore = window.confirm('Restore unsaved draft from ' + new Date(saved.ts).toLocaleString() + '?');
          if (restore) {
            applyDraft(form, saved);
            grid.dirty = true;
            updateDraftBar(grid);
          } else {
            localStorage.removeItem(key);
          }
        }
      } catch (err) { /* ignore */ }
      form.setAttribute('data-spreadsheet-draft-applied', '');
    }

    grid.draftTimer = window.setInterval(function () {
      if (!grid.dirty) return;
      try {
        localStorage.setItem(key, serializeForm(form));
        if (grid.draftBar) {
          grid.draftBar.textContent = 'Draft saved ' + new Date().toLocaleTimeString();
          grid.draftBar.classList.remove('erp-spreadsheet-draft-bar--dirty');
          grid.draftBar.classList.add('erp-spreadsheet-draft-bar--saved');
        }
      } catch (err) { /* ignore */ }
    }, DRAFT_INTERVAL_MS);
  }

  function bindBeforeUnload(grid) {
    var form = grid.form;
    if (!form) return;
    window.addEventListener('beforeunload', function (event) {
      if (!grid.dirty) return;
      event.preventDefault();
      event.returnValue = '';
    });
  }

  function bindAjaxSubmit(grid) {
    var form = grid.form;
    if (!form || !form.hasAttribute('data-spreadsheet-ajax')) return;

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      saveScrollPosition(grid);
      var scrollTop = grid.scrollEl.scrollTop;
      var scrollLeft = grid.scrollEl.scrollLeft;
      var active = document.activeElement;
      var activePos = isEditable(active) ? cellPosition(active) : null;

      var fd = new FormData(form);
      var action = form.getAttribute('action') || window.location.href;
      var method = (form.getAttribute('method') || 'POST').toUpperCase();

      fetch(action, {
        method: method,
        body: fd,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (res) {
          if (!res.ok) throw new Error('Save failed (' + res.status + ')');
          return res.json().catch(function () { return { ok: true }; });
        })
        .then(function (data) {
          grid.dirty = false;
          try { localStorage.removeItem(draftKey(form)); } catch (err) { /* ignore */ }
          if (grid.draftBar) {
            grid.draftBar.textContent = 'Saved';
            grid.draftBar.classList.remove('erp-spreadsheet-draft-bar--dirty');
            grid.draftBar.classList.add('erp-spreadsheet-draft-bar--saved');
          }
          grid.table.querySelectorAll('[data-spreadsheet-row--dirty]').forEach(function (row) {
            row.removeAttribute('data-spreadsheet-row--dirty');
          });
          grid.scrollEl.scrollTop = scrollTop;
          grid.scrollEl.scrollLeft = scrollLeft;
          if (activePos) {
            window.setTimeout(function () {
              focusTableAt(grid.table, activePos.rowIndex, activePos.cellIndex);
            }, 0);
          }
          form.dispatchEvent(new CustomEvent('maxek:spreadsheet-saved', { bubbles: true, detail: data }));
        })
        .catch(function (err) {
          window.alert(err.message || 'Could not save. Please try again.');
        });
    });
  }

  function bindRowMutations(grid) {
    var body = grid.table.tBodies[0];
    if (!body) return;

    var observer = new MutationObserver(function () {
      var count = tagRows(grid.table);
      grid.wrapper.classList.toggle('erp-spreadsheet-grid--virtual', count >= VIRTUAL_THRESHOLD);
      restoreScrollPosition(grid);
    });
    observer.observe(body, { childList: true });
  }

  function createDraftBar(wrapper) {
    var bar = document.createElement('div');
    bar.className = 'erp-spreadsheet-draft-bar';
    bar.textContent = 'Ready';
    wrapper.appendChild(bar);
    return bar;
  }

  function initGrid(table) {
    if (grids.has(table)) return grids.get(table);

    var wrapped = wrapTable(table);
    if (!wrapped) {
      var existing = table.closest('.erp-spreadsheet-grid');
      if (!existing) return null;
      wrapped = {
        wrapper: existing,
        scroll: existing.querySelector('.erp-spreadsheet-grid__scroll') || existing,
        table: table,
      };
    }

    var form = table.closest('form');
    var rowCount = tagRows(table);
    if (rowCount >= VIRTUAL_THRESHOLD) {
      wrapped.wrapper.classList.add('erp-spreadsheet-grid--virtual');
    }

    var draftBar = null;
    if (form && !form.hasAttribute('data-spreadsheet-no-draft')) {
      draftBar = wrapped.wrapper.querySelector('.erp-spreadsheet-draft-bar');
      if (!draftBar) draftBar = createDraftBar(wrapped.wrapper);
    }

    var grid = {
      wrapper: wrapped.wrapper,
      scrollEl: wrapped.scroll,
      table: table,
      form: form,
      dirty: false,
      draftBar: draftBar,
      draftTimer: null,
    };

    bindKeyboard(grid);
    bindScrollPreserve(grid);
    bindDirtyTracking(grid);
    bindDraftAutoSave(grid);
    bindBeforeUnload(grid);
    bindAjaxSubmit(grid);
    bindRowMutations(grid);

    restoreScrollPosition(grid);
    grids.set(table, grid);
    return grid;
  }

  function findEligibleTables() {
    var selectors = [
      'table[data-spreadsheet-grid]',
      'table[data-entry-table]',
      'table[data-lines-table]',
      '.erp-data-entry-panel table.erp-table-entry',
      'form[data-timesheet-form] table.erp-table',
      'form[data-dpr-form] table.erp-table',
      '#measurement-sheet-table',
      '#boq-lines-table',
      '#extra-lines-table',
      'form[data-payroll-generate-form] ~ .erp-table-panel table.erp-table-module',
    ];
    var seen = new Set();
    var result = [];

    selectors.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (table) {
        if (seen.has(table)) return;
        if (!table.querySelector('tbody input, tbody select, tbody textarea')) return;
        seen.add(table);
        result.push(table);
      });
    });

    document.querySelectorAll('.erp-data-entry-panel table.erp-table-module').forEach(function (table) {
      if (seen.has(table)) return;
      if (!table.querySelector('tbody input, tbody select, tbody textarea')) return;
      seen.add(table);
      result.push(table);
    });

    return result;
  }

  function insertRowAfterCurrent(table, newRow) {
    var active = document.activeElement;
    var currentRow = active && active.closest ? active.closest('tbody tr') : null;
    var body = table.tBodies[0];
    if (!body) {
      body.appendChild(newRow);
      return newRow;
    }
    if (currentRow && currentRow.parentElement === body && table.contains(currentRow)) {
      currentRow.insertAdjacentElement('afterend', newRow);
    } else {
      body.appendChild(newRow);
    }
    saveScrollPosition(grids.get(table) || { scrollEl: table.closest('.erp-spreadsheet-grid__scroll') });
    var grid = grids.get(table);
    if (grid) {
      grid.dirty = true;
      updateDraftBar(grid);
      markRowDirty(newRow);
    }
    if (window.MaxekDataEntry && window.MaxekDataEntry.focusFirstField) {
      window.MaxekDataEntry.focusFirstField(newRow);
    }
    return newRow;
  }

  function preserveAndRun(fn) {
    return function () {
      var tables = findEligibleTables();
      tables.forEach(function (table) {
        var grid = grids.get(table);
        if (grid) saveScrollPosition(grid);
      });
      var result = fn.apply(this, arguments);
      tables.forEach(function (table) {
        var grid = grids.get(table);
        if (grid) restoreScrollPosition(grid);
      });
      return result;
    };
  }

  function init() {
    findEligibleTables().forEach(initGrid);

    document.addEventListener('maxek:entry-opened', function () {
      window.setTimeout(function () {
        findEligibleTables().forEach(initGrid);
      }, 80);
    });

    document.addEventListener('maxek:row-added', function (event) {
      var row = event.detail && event.detail.row;
      if (row) {
        var table = row.closest('table');
        if (table) initGrid(table);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.MaxekSpreadsheetGrid = {
    init: init,
    initGrid: initGrid,
    insertRowAfterCurrent: insertRowAfterCurrent,
    moveFocus: moveFocus,
    focusTableAt: focusTableAt,
    highlightActiveCell: highlightActiveCell,
    saveScrollPosition: function (table) {
      var grid = grids.get(table);
      if (grid) saveScrollPosition(grid);
    },
    restoreScrollPosition: function (table) {
      var grid = grids.get(table);
      if (grid) restoreScrollPosition(grid);
    },
    preserveAndRun: preserveAndRun,
    markDirty: function (table) {
      var grid = grids.get(table);
      if (grid) {
        grid.dirty = true;
        updateDraftBar(grid);
      }
    },
  };
})();
