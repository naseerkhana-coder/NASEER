(function () {
  function parseDob(dobStr) {
    if (!dobStr) return null;
    var parts = dobStr.split('-');
    if (parts.length !== 3) return null;
    var dob = new Date(
      parseInt(parts[0], 10),
      parseInt(parts[1], 10) - 1,
      parseInt(parts[2], 10)
    );
    return isNaN(dob.getTime()) ? null : dob;
  }

  function calcAgeParts(dobStr) {
    var dob = parseDob(dobStr);
    if (!dob) return null;
    var today = new Date();
    var years = today.getFullYear() - dob.getFullYear();
    var months = today.getMonth() - dob.getMonth();
    var days = today.getDate() - dob.getDate();
    if (days < 0) {
      months -= 1;
    }
    if (months < 0) {
      years -= 1;
      months += 12;
    }
    if (years < 0) return null;
    return { years: years, months: months };
  }

  function formatAge(parts) {
    if (!parts) return '';
    if (parts.months > 0) {
      return parts.years + ' Years ' + parts.months + ' Months';
    }
    return parts.years + ' Years';
  }

  function findAgeDisplay(input) {
    var wrap = input.closest('[data-dob-age]');
    if (wrap) {
      var inWrap = wrap.querySelector('[data-age-display]');
      if (inWrap) return inWrap;
    }
    var dobField = input.closest('.erp-field');
    if (dobField) {
      var sibling = dobField.nextElementSibling;
      if (sibling) {
        if (sibling.matches('[data-age-display]')) return sibling;
        var nested = sibling.querySelector('[data-age-display]');
        if (nested) return nested;
      }
    }
    var form = input.closest('form');
    if (form) {
      var displays = form.querySelectorAll('[data-age-display]');
      if (displays.length === 1) return displays[0];
    }
    return document.querySelector('[data-age-display]');
  }

  function setAgeDisplay(display, text) {
    if (!display) return;
    if (display.tagName === 'INPUT' || display.tagName === 'TEXTAREA') {
      display.value = text;
      display.classList.toggle('has-value', !!text);
    } else {
      display.textContent = text || '—';
    }
  }

  function bindDobInput(input) {
    if (input.dataset.dobAgeBound === '1') return;
    var display = findAgeDisplay(input);
    if (!display) return;
    input.dataset.dobAgeBound = '1';

    function refresh() {
      var text = formatAge(calcAgeParts(input.value));
      setAgeDisplay(display, text);
    }

    input.addEventListener('change', refresh);
    input.addEventListener('input', refresh);
    refresh();
  }

  function init() {
    document.querySelectorAll('[data-dob-input]').forEach(bindDobInput);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.MaxekDobAge = { refresh: init, formatAge: formatAge, calcAgeParts: calcAgeParts };
})();
