document.addEventListener('DOMContentLoaded', function () {
  const layout = document.querySelector('.maxek-layout');
  const sidebar = document.querySelector('.command-centre-rail') || document.querySelector('.maxek-mobile-nav') || document.querySelector('.tool-rail');
  const toggle = document.querySelector('[data-sidebar-toggle]');
  const overlay = document.querySelector('.sidebar-overlay');
  const subbar = document.getElementById('department-subbar');
  const subbarReopen = document.querySelector('[data-subbar-reopen]');
  const SUBBAR_STORAGE_PREFIX = 'maxek-subbar-collapsed:';
  const LEGACY_SUBBAR_KEY = 'maxek-subbar-collapsed';

  function getSubbarSlug() {
    return subbar ? subbar.getAttribute('data-subbar-key') || subbar.getAttribute('data-subbar-slug') || '' : '';
  }

  function subbarStorageKey(slug) {
    return SUBBAR_STORAGE_PREFIX + (slug || 'default');
  }

  function isSubbarCollapsedForSlug(slug) {
    if (!slug) return false;
    try {
      return sessionStorage.getItem(subbarStorageKey(slug)) === '1';
    } catch (err) {
      return false;
    }
  }

  function setSubbarCollapsed(slug, collapsed) {
    if (!slug) return;
    try {
      if (collapsed) {
        sessionStorage.setItem(subbarStorageKey(slug), '1');
      } else {
        sessionStorage.removeItem(subbarStorageKey(slug));
      }
      sessionStorage.removeItem(LEGACY_SUBBAR_KEY);
    } catch (err) {
      /* ignore storage errors */
    }
  }

  function syncSubbarVisibility() {
    if (!subbar) return;
    const slug = getSubbarSlug();
    const collapsed = isSubbarCollapsedForSlug(slug);
    subbar.classList.toggle('is-collapsed', collapsed);
    if (subbarReopen) {
      subbarReopen.hidden = !collapsed;
      subbarReopen.classList.toggle('is-visible', collapsed);
    }
  }

  function closeSidebar() {
    sidebar?.classList.remove('open');
    overlay?.classList.remove('visible');
    toggle?.setAttribute('aria-expanded', 'false');
    const icon = toggle?.querySelector('i');
    if (icon) {
      icon.classList.remove('fa-xmark');
      icon.classList.add('fa-bars');
    }
  }

  function openSidebar() {
    sidebar?.classList.add('open');
    sidebar?.removeAttribute('hidden');
    overlay?.classList.add('visible');
    toggle?.setAttribute('aria-expanded', 'true');
    const icon = toggle?.querySelector('i');
    if (icon) {
      icon.classList.remove('fa-bars');
      icon.classList.add('fa-xmark');
    }
  }

  document.querySelectorAll('.maxek-top-nav--drawer .maxek-top-nav-trigger').forEach(function (button) {
    button.addEventListener('click', function () {
      const item = button.closest('.maxek-top-nav-item');
      if (!item) return;
      const isOpen = item.classList.contains('is-open');
      item.parentElement?.querySelectorAll('.maxek-top-nav-item.is-open').forEach(function (openItem) {
        if (openItem !== item) {
          openItem.classList.remove('is-open');
          openItem.querySelector('.maxek-top-nav-trigger')?.setAttribute('aria-expanded', 'false');
        }
      });
      item.classList.toggle('is-open', !isOpen);
      button.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
    });
  });

  function initHorizontalTopNavDropdowns() {
    const horizontalNav = document.querySelector('.maxek-top-nav--horizontal');
    if (!horizontalNav) return;

    horizontalNav.querySelectorAll('.maxek-top-nav-item.has-children').forEach(function (item) {
      const trigger = item.querySelector('.maxek-top-nav-trigger');
      const dropdown = item.querySelector('.maxek-top-nav-dropdown');
      if (!trigger || !dropdown) return;

      function positionDropdown() {
        const rect = trigger.getBoundingClientRect();
        dropdown.style.setProperty('--maxek-dropdown-top', rect.bottom + 'px');
        dropdown.style.setProperty('--maxek-dropdown-left', Math.max(8, rect.left) + 'px');
      }

      function closeOtherItems(exceptItem) {
        horizontalNav.querySelectorAll('.maxek-top-nav-item.is-open').forEach(function (openItem) {
          if (openItem === exceptItem) return;
          openItem.classList.remove('is-open');
          openItem.querySelector('.maxek-top-nav-trigger')?.setAttribute('aria-expanded', 'false');
        });
      }

      function setOpen(open) {
        item.classList.toggle('is-open', open);
        trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
          closeOtherItems(item);
          positionDropdown();
        }
      }

      item.addEventListener('mouseenter', function () {
        setOpen(true);
      });

      item.addEventListener('mouseleave', function (event) {
        if (event.relatedTarget && item.contains(event.relatedTarget)) return;
        setOpen(false);
      });

      item.addEventListener('focusin', function () {
        setOpen(true);
      });

      item.addEventListener('focusout', function (event) {
        if (event.relatedTarget && item.contains(event.relatedTarget)) return;
        setOpen(false);
      });

      trigger.addEventListener('click', function () {
        setOpen(!item.classList.contains('is-open'));
      });

      window.addEventListener('resize', function () {
        if (item.classList.contains('is-open')) {
          positionDropdown();
        }
      });

      window.addEventListener('scroll', function () {
        if (item.classList.contains('is-open')) {
          positionDropdown();
        }
      }, true);
    });
  }

  initHorizontalTopNavDropdowns();

  function bindAnchorLinks(selector, activeClass) {
    document.querySelectorAll(selector).forEach(function (link) {
      link.addEventListener('click', function (event) {
        const anchorId = link.getAttribute('data-module-anchor');
        if (!anchorId) return;
        let linkUrl;
        try {
          linkUrl = new URL(link.href, window.location.origin);
        } catch (err) {
          return;
        }
        if (linkUrl.pathname !== window.location.pathname) {
          return;
        }
        const target = document.getElementById(anchorId);
        if (!target) {
          return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', linkUrl.pathname + linkUrl.search + '#' + anchorId);
        link.closest(activeClass.container)?.querySelectorAll(activeClass.link).forEach(function (item) {
          item.classList.toggle('active', item === link);
        });
      });
    });
  }

  bindAnchorLinks('.maxek-top-nav-dropdown-link[data-module-anchor]', {
    container: '.maxek-top-nav-dropdown',
    link: '.maxek-top-nav-dropdown-link',
  });

  toggle?.addEventListener('click', function () {
    if (sidebar?.classList.contains('open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  document.querySelectorAll('[data-sidebar-close]').forEach(function (button) {
    button.addEventListener('click', closeSidebar);
  });

  overlay?.addEventListener('click', closeSidebar);

  const deptMenuToggle = document.querySelector('[data-dept-menu-toggle]');
  const deptMenu = document.querySelector('[data-dept-menu]');

  function syncDeptMenuToggle() {
    if (!deptMenuToggle || !deptMenu) return;
    const isOpen = deptMenu.classList.contains('is-open');
    deptMenuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  deptMenuToggle?.addEventListener('click', function () {
    if (!deptMenu) return;
    deptMenu.classList.toggle('is-open');
    syncDeptMenuToggle();
  });

  window.addEventListener('resize', function () {
    if (!deptMenu || !deptMenuToggle) return;
    if (window.innerWidth > 900 && deptMenu.classList.contains('is-open')) {
      deptMenu.classList.remove('is-open');
      syncDeptMenuToggle();
    }
  });

  document.querySelectorAll('[data-subbar-close]').forEach(function (button) {
    button.addEventListener('click', function () {
      setSubbarCollapsed(getSubbarSlug(), true);
      syncSubbarVisibility();
    });
  });

  subbarReopen?.addEventListener('click', function () {
    setSubbarCollapsed(getSubbarSlug(), false);
    syncSubbarVisibility();
  });

  if (subbar) {
    try {
      sessionStorage.removeItem(LEGACY_SUBBAR_KEY);
    } catch (err) {
      /* ignore storage errors */
    }
    syncSubbarVisibility();
    subbar.querySelectorAll('a.department-subbar-link[data-module-anchor]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        const anchorId = link.getAttribute('data-module-anchor');
        if (!anchorId) return;
        let linkUrl;
        try {
          linkUrl = new URL(link.href, window.location.origin);
        } catch (err) {
          return;
        }
        if (linkUrl.pathname !== window.location.pathname) {
          return;
        }
        const target = document.getElementById(anchorId);
        if (!target) {
          return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', linkUrl.pathname + linkUrl.search + '#' + anchorId);
        subbar.querySelectorAll('.department-subbar-link').forEach(function (item) {
          item.classList.toggle('active', item === link);
        });
      });
    });
  }

  const datetimeEl = document.getElementById('header-datetime');
  if (datetimeEl) {
    const tz = datetimeEl.getAttribute('data-timezone') || 'Asia/Kolkata';
    const formatter = new Intl.DateTimeFormat('en-IN', {
      timeZone: tz,
      weekday: 'long',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });

    function refreshHeaderClock() {
      const parts = formatter.formatToParts(new Date());
      const pick = function (type) {
        const part = parts.find(function (item) { return item.type === type; });
        return part ? part.value : '';
      };
      const weekday = pick('weekday');
      const day = pick('day');
      const month = pick('month');
      const year = pick('year');
      const hour = pick('hour');
      const minute = pick('minute');
      datetimeEl.textContent = weekday + ', ' + day + ' ' + month + ' ' + year + ' | ' + hour + ':' + minute;
    }

    refreshHeaderClock();
    window.setInterval(refreshHeaderClock, 30000);
  }

  document.querySelectorAll('[data-modal-open]').forEach(function (button) {
    button.addEventListener('click', function () {
      const modal = document.getElementById(button.getAttribute('data-modal-open'));
      if (!modal) return;
      modal.hidden = false;
      const firstField = modal.querySelector('input, select, textarea, button');
      firstField?.focus();
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(function (control) {
    control.addEventListener('click', function () {
      const modal = control.closest('.erp-modal');
      if (modal) modal.hidden = true;
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('.erp-modal:not([hidden])').forEach(function (modal) {
      modal.hidden = true;
    });
  });

  document.querySelectorAll('.rail-group').forEach(function (group) {
    group.addEventListener('toggle', function () {
      if (!group.open) return;
      document.querySelectorAll('.rail-group[open]').forEach(function (other) {
        if (other !== group && !other.querySelector('.rail-subbtn.active')) {
          other.open = false;
        }
      });
    });
  });

  document.querySelectorAll('.rail-subbtn[data-module-anchor]').forEach(function (link) {
    link.addEventListener('click', function (event) {
      const anchorId = link.getAttribute('data-module-anchor');
      if (!anchorId) return;
      let linkUrl;
      try {
        linkUrl = new URL(link.href, window.location.origin);
      } catch (err) {
        return;
      }
      if (linkUrl.pathname !== window.location.pathname) {
        return;
      }
      const target = document.getElementById(anchorId);
      if (!target) {
        return;
      }
      event.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      history.replaceState(null, '', linkUrl.pathname + linkUrl.search + '#' + anchorId);
      link.closest('.rail-subnav')?.querySelectorAll('.rail-subbtn').forEach(function (item) {
        item.classList.toggle('active', item === link);
      });
    });
  });

  function findModuleTablePanel(fromNode) {
    const layout = fromNode.closest('.erp-module-layout');
    if (layout) {
      const panels = layout.querySelectorAll('[data-erp-table]');
      for (let i = 0; i < panels.length; i += 1) {
        const panel = panels[i];
        if (!panel.classList.contains('erp-module-table-panel--hidden') && panel.offsetParent !== null) {
          return panel;
        }
      }
      return layout.querySelector('[data-erp-table]');
    }
    return fromNode.closest('[data-erp-table]');
  }

  document.querySelectorAll('[data-table-search], [data-erp-module-search]').forEach(function (input) {
    if (input.hasAttribute('name') && input.closest('form[method="get"]')) {
      return;
    }
    const panel = findModuleTablePanel(input);
    const table = panel?.querySelector('table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    input.addEventListener('input', function () {
      const term = input.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach(function (row) {
        const match = row.textContent.toLowerCase().includes(term);
        row.style.display = match ? '' : 'none';
        if (match) visible += 1;
      });
      const info = panel.querySelector('[data-page-info]');
      if (info) {
        info.textContent = term
          ? 'Showing ' + visible + ' matching record' + (visible === 1 ? '' : 's')
          : 'Showing ' + rows.length + ' record' + (rows.length === 1 ? '' : 's');
      }
    });
  });

  document.querySelectorAll('[data-table-export]').forEach(function (button) {
    button.addEventListener('click', function () {
      const exportUrl = button.getAttribute('data-export-url');
      if (exportUrl) {
        window.location.href = exportUrl;
        return;
      }
      const panel = findModuleTablePanel(button);
      const table = panel?.querySelector('table');
      if (!table) return;
      const rows = Array.from(table.querySelectorAll('tr'))
        .filter(function (row) { return row.style.display !== 'none'; })
        .map(function (row) {
          return Array.from(row.children).map(function (cell) {
            return '"' + cell.textContent.trim().replace(/"/g, '""') + '"';
          }).join(',');
        });
      const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = (button.getAttribute('data-table-export') || 'export') + '.csv';
      link.click();
      URL.revokeObjectURL(link.href);
    });
  });

  document.querySelectorAll('[data-erp-print]').forEach(function (button) {
    button.addEventListener('click', function () {
      const targetSelector = button.getAttribute('data-erp-print-target');
      if (!targetSelector) {
        window.print();
        return;
      }
      const target = document.querySelector(targetSelector);
      if (!target) {
        window.print();
        return;
      }
      document.body.classList.add('erp-print-table-only');
      target.classList.add('erp-print-focus');
      window.print();
      window.addEventListener('afterprint', function cleanup() {
        document.body.classList.remove('erp-print-table-only');
        target.classList.remove('erp-print-focus');
        window.removeEventListener('afterprint', cleanup);
      });
    });
  });

  document.querySelectorAll('[data-erp-add-trigger]').forEach(function (button) {
    button.addEventListener('click', function () {
      const selector = button.getAttribute('data-erp-add-trigger');
      if (!selector) return;
      const trigger = document.querySelector(selector);
      if (trigger) {
        trigger.click();
      }
    });
  });

  document.querySelectorAll('.erp-field input, .erp-field select, .erp-field textarea').forEach(function (field) {
    function sync() {
      field.classList.toggle('has-value', field.value !== '');
    }
    field.addEventListener('input', sync);
    field.addEventListener('change', sync);
    sync();
  });

  const category = document.getElementById('worker_category');
  const subcontractorRow = document.getElementById('subcontractor-row');
  if (category && subcontractorRow) {
    function toggleSubcontractor() {
      subcontractorRow.style.display = category.value === 'Sub Contractor Staff' ? '' : 'none';
    }
    category.addEventListener('change', toggleSubcontractor);
    toggleSubcontractor();
  }

  function activateDashView(root, viewName, options) {
    const opts = options || {};
    const normalized = viewName === 'operations' ? 'operations' : 'overview';
    root.querySelectorAll('[data-dash-tab]').forEach(function (tab) {
      const isActive = tab.getAttribute('data-dash-tab') === normalized;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    root.querySelectorAll('[data-dash-panel]').forEach(function (panel) {
      const isActive = panel.getAttribute('data-dash-panel') === normalized;
      panel.classList.toggle('active', isActive);
      if (isActive) {
        panel.removeAttribute('hidden');
      } else {
        panel.setAttribute('hidden', '');
      }
    });
    document.querySelectorAll('[data-dash-subbar-anchor]').forEach(function (link) {
      link.classList.toggle('active', link.getAttribute('data-dash-subbar-anchor') === normalized);
    });
    if (opts.updateHash !== false) {
      const nextHash = normalized === 'operations' ? '#operations' : '#overview';
      if (window.location.hash !== nextHash) {
        history.replaceState(null, '', window.location.pathname + window.location.search + nextHash);
      }
    }
  }

  document.querySelectorAll('[data-dash-tabs]').forEach(function (root) {
    root.querySelectorAll('[data-dash-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        activateDashView(root, tab.getAttribute('data-dash-tab') || 'overview');
      });
    });

    root.querySelectorAll('[data-dash-subbar-anchor]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        const anchor = link.getAttribute('data-dash-subbar-anchor') || 'overview';
        activateDashView(root, anchor, { updateHash: false });
      });
    });

    function syncDashFromHash() {
      const hash = (window.location.hash || '').replace('#', '').toLowerCase();
      const view = hash === 'operations' ? 'operations' : 'overview';
      activateDashView(root, view, { updateHash: hash !== 'operations' && hash !== 'overview' });
    }

    syncDashFromHash();
    window.addEventListener('hashchange', syncDashFromHash);
  });

  /* ── MAXEK Shell Standard: global search, panels, help ── */
  const globalSearchModal = document.getElementById('global-search-modal');
  const globalSearchInput = document.getElementById('global-search-input');
  const headerSearchTrigger = document.getElementById('header-search-trigger');
  let activeSearchCategory = 'all';

  function openGlobalSearch() {
    if (!globalSearchModal) return;
    globalSearchModal.hidden = false;
    globalSearchInput?.focus();
  }

  function closeGlobalSearch() {
    if (!globalSearchModal) return;
    globalSearchModal.hidden = true;
  }

  document.querySelectorAll('[data-global-search-open]').forEach(function (btn) {
    btn.addEventListener('click', openGlobalSearch);
  });

  headerSearchTrigger?.addEventListener('click', openGlobalSearch);
  headerSearchTrigger?.addEventListener('focus', openGlobalSearch);

  globalSearchModal?.querySelector('[data-global-search-close]')?.addEventListener('click', closeGlobalSearch);

  document.querySelectorAll('.global-search-cat').forEach(function (btn) {
    btn.addEventListener('click', function () {
      activeSearchCategory = btn.getAttribute('data-search-category') || 'project';
      document.querySelectorAll('.global-search-cat').forEach(function (b) {
        b.classList.toggle('is-active', b === btn);
      });
    });
  });

  document.getElementById('global-search-submit')?.addEventListener('click', function () {
    runGlobalSearch();
  });

  let searchDebounceTimer;
  function runGlobalSearch() {
    const q = (globalSearchInput?.value || '').trim();
    const results = document.getElementById('global-search-results');
    if (!results) return;
    if (q.length < 2) {
      results.hidden = false;
      results.innerHTML = '<p class="global-search-hint">Type at least 2 characters.</p>';
      return;
    }
    results.hidden = false;
    results.innerHTML = '<p class="global-search-hint">Searching…</p>';
    const params = new URLSearchParams({ q: q, category: activeSearchCategory, limit: '12' });
    fetch('/api/erp/search?' + params.toString(), { credentials: 'same-origin' })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        const items = data.results || [];
        if (!items.length) {
          results.innerHTML = '<p class="global-search-hint">No results found.</p>';
          return;
        }
        results.innerHTML = '<ul class="global-search-result-list"></ul>';
        const list = results.querySelector('.global-search-result-list');
        items.forEach(function (hit) {
          const li = document.createElement('li');
          const a = document.createElement('a');
          a.href = hit.url || '#';
          a.className = 'global-search-result-item';
          a.innerHTML = '<strong>' + hit.label + '</strong><span>' + (hit.subtitle || hit.category) + '</span>';
          a.addEventListener('click', function () { closeGlobalSearch(); });
          li.appendChild(a);
          list.appendChild(li);
        });
      })
      .catch(function () {
        results.innerHTML = '<p class="global-search-hint">Search failed. Try again.</p>';
      });
  }

  globalSearchInput?.addEventListener('input', function () {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(runGlobalSearch, 280);
  });

  globalSearchInput?.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      runGlobalSearch();
    }
  });

  function postWorkContext(payload) {
    return fetch('/api/erp/context', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  const companySelect = document.querySelector('[data-company-select]');
  const branchSelect = document.querySelector('[data-branch-select]');
  const projectSelect = document.querySelector('[data-project-select]');

  companySelect?.addEventListener('change', function () {
    const opt = companySelect.options[companySelect.selectedIndex];
    postWorkContext({
      company_id: companySelect.value || null,
      company_code: opt?.getAttribute('data-code') || '',
    }).then(function () { window.location.reload(); });
  });

  branchSelect?.addEventListener('change', function () {
    postWorkContext({
      branch_name: branchSelect.value,
    }).then(function () { window.location.reload(); });
  });

  projectSelect?.addEventListener('change', function () {
    postWorkContext({
      project_id: projectSelect.value || null,
    });
  });

  function refreshLiveBadges() {
    fetch('/api/erp/badges', { credentials: 'same-origin' })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        const badges = data.badges || {};
        document.querySelectorAll('.department-subbar-badge').forEach(function (el) {
          const link = el.closest('a');
          if (!link) return;
          const href = link.getAttribute('href') || '';
          if (href.indexOf('material-request') >= 0) el.textContent = badges.material_request || '';
          if (href.indexOf('purchase-request') >= 0) el.textContent = badges.purchase_request || '';
        });
        const approvalBadge = document.querySelector('.header-icon-btn[href*="approvals"] .header-badge');
        if (approvalBadge && badges.pending_approval) {
          approvalBadge.textContent = badges.pending_approval;
        }
        const expiryEl = document.getElementById('expiry-alert-count');
        if (expiryEl && badges.store_alerts) {
          expiryEl.textContent = badges.store_alerts;
          expiryEl.hidden = false;
        }
      })
      .catch(function () { /* ignore */ });
  }

  refreshLiveBadges();
  window.setInterval(refreshLiveBadges, 60000);

  document.querySelectorAll('[data-attachments-panel]').forEach(function (panel) {
    const table = panel.getAttribute('data-record-table');
    const recordId = panel.getAttribute('data-record-id');
    const moduleId = panel.getAttribute('data-module-id') || '';
    const listEl = panel.querySelector('[data-attachments-list]');
    const form = panel.querySelector('[data-attachment-upload]');

    function loadAttachments() {
      if (!table || !recordId || !listEl) return;
      fetch('/api/erp/attachments/' + encodeURIComponent(table) + '/' + recordId, { credentials: 'same-origin' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          const items = data.attachments || [];
          listEl.innerHTML = items.length
            ? items.map(function (a) {
              return '<a class="universal-attachment-link" href="/api/erp/attachments/' + a.id + '/download">' +
                a.original_filename + '</a>';
            }).join('')
            : '<p class="global-search-hint">No attachments.</p>';
        });
    }

    loadAttachments();
    form?.addEventListener('submit', function (event) {
      event.preventDefault();
      const fd = new FormData(form);
      fd.append('module_id', moduleId);
      fd.append('record_table', table);
      fd.append('record_id', recordId);
      fetch('/api/erp/attachments', { method: 'POST', credentials: 'same-origin', body: fd })
        .then(function () { loadAttachments(); form.reset(); });
    });
  });

  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (globalSearchModal && !globalSearchModal.hidden) {
        closeGlobalSearch();
      } else {
        openGlobalSearch();
      }
    }
    if (event.key === 'Escape' && globalSearchModal && !globalSearchModal.hidden) {
      closeGlobalSearch();
    }
  });

  function bindPanelToggle(panelId, toggleSelector, reopenSelector, storageKey) {
    const panel = document.getElementById(panelId);
    const reopen = document.querySelector(reopenSelector);
    if (!panel) return;

    function setCollapsed(collapsed) {
      panel.classList.toggle('is-collapsed', collapsed);
      if (reopen) reopen.hidden = !collapsed;
      try {
        if (collapsed) sessionStorage.setItem(storageKey, '1');
        else sessionStorage.removeItem(storageKey);
      } catch (err) { /* ignore */ }
    }

    try {
      if (sessionStorage.getItem(storageKey) === '1') setCollapsed(true);
    } catch (err) { /* ignore */ }

    document.querySelectorAll(toggleSelector).forEach(function (btn) {
      btn.addEventListener('click', function () {
        setCollapsed(!panel.classList.contains('is-collapsed'));
      });
    });

    reopen?.addEventListener('click', function () {
      setCollapsed(false);
    });
  }

  bindPanelToggle('shell-quick-panel', '[data-quick-panel-toggle]', '[data-quick-panel-reopen]', 'maxek-quick-panel-collapsed');
  bindPanelToggle('shell-action-panel', '[data-action-panel-toggle]', '[data-action-panel-reopen]', 'maxek-action-panel-collapsed');

  const helpDrawer = document.getElementById('shell-help-drawer');
  const helpToggle = document.querySelector('[data-help-drawer-toggle]');

  helpToggle?.addEventListener('click', function () {
    if (!helpDrawer) return;
    const open = helpDrawer.hidden;
    helpDrawer.hidden = !open;
    helpToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.querySelector('[data-help-drawer-close]')?.addEventListener('click', function () {
    if (helpDrawer) helpDrawer.hidden = true;
    helpToggle?.setAttribute('aria-expanded', 'false');
  });

  const quickActionsToggle = document.querySelector('[data-quick-actions-toggle]');
  const quickActionsMenu = document.querySelector('.header-quick-menu');

  quickActionsToggle?.addEventListener('click', function (event) {
    event.stopPropagation();
    if (!quickActionsMenu) return;
    const open = quickActionsMenu.hidden;
    quickActionsMenu.hidden = !open;
    quickActionsToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.addEventListener('click', function () {
    if (quickActionsMenu && !quickActionsMenu.hidden) {
      quickActionsMenu.hidden = true;
      quickActionsToggle?.setAttribute('aria-expanded', 'false');
    }
  });

  /* Back navigates to previous screen or explicit href; Close goes to dashboard */
  document.querySelectorAll('[data-erp-back]').forEach(function (btn) {
    btn.addEventListener('click', function (event) {
      if (btn.tagName === 'A') return;
      event.preventDefault();
      const href = btn.getAttribute('data-back-href');
      if (href) {
        window.location.href = href;
        return;
      }
      if (window.history.length > 1) {
        window.history.back();
      } else {
        window.location.href = btn.getAttribute('data-dashboard-url') || '/dashboard';
      }
    });
  });

  document.querySelectorAll('.global-search-cat').forEach(function (btn, index) {
    if (index === 0) btn.classList.add('is-active');
  });
});
