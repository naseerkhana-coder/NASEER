/**
 * MAXEK ERP — Corporate report print/export action bar
 */
(function () {
  'use strict';

  function getBar(root) {
    return root || document.querySelector('[data-report-actions]');
  }

  function verifyUrl(bar) {
    var slug = bar.getAttribute('data-report-slug') || '';
    var code = bar.getAttribute('data-verification-code') || '';
    var doc = bar.getAttribute('data-document-number') || '';
    var origin = window.location.origin || '';
    return origin + '/reports/verify?slug=' + encodeURIComponent(slug)
      + '&doc=' + encodeURIComponent(doc)
      + '&code=' + encodeURIComponent(code);
  }

  function drawQrPlaceholder(container, text) {
    if (!container) return;
    container.innerHTML = '';
    var canvas = document.createElement('canvas');
    canvas.width = 144;
    canvas.height = 144;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, 144, 144);
    ctx.strokeStyle = '#232323';
    ctx.lineWidth = 2;
    ctx.strokeRect(4, 4, 136, 136);
    ctx.fillStyle = '#E30613';
    ctx.font = 'bold 11px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('MAXEK QR', 72, 30);
    ctx.fillStyle = '#232323';
    ctx.font = '9px monospace';
    var code = (text || '').slice(0, 12);
    ctx.fillText(code, 72, 80);
    ctx.font = '8px Arial';
    ctx.fillStyle = '#666';
    ctx.fillText('Scan to verify', 72, 110);
    container.appendChild(canvas);
  }

  function handlePrint() {
    window.print();
  }

  function handleExcel(bar) {
    var url = bar.getAttribute('data-export-url');
    if (url) {
      window.location.href = url;
      return;
    }
    alert('Excel export URL not configured for this report.');
  }

  function handleEmail(bar) {
    var subject = encodeURIComponent(bar.getAttribute('data-email-subject') || 'MAXEK Report');
    var body = encodeURIComponent(
      'Please find the MAXEK report attached or view at: ' + window.location.href
      + '\n\nVerification code: ' + (bar.getAttribute('data-verification-code') || '')
    );
    window.location.href = 'mailto:?subject=' + subject + '&body=' + body;
  }

  function handleWhatsApp(bar) {
    var text = encodeURIComponent(
      'MAXEK Report — ' + (bar.getAttribute('data-document-number') || 'Document')
      + '\nVerify: ' + verifyUrl(bar)
    );
    window.open('https://wa.me/?text=' + text, '_blank', 'noopener');
  }

  function handleQr(bar) {
    var panel = bar.querySelector('[data-qr-panel]');
    if (!panel) return;
    var hidden = panel.hasAttribute('hidden');
    panel.hidden = !hidden;
    if (!hidden) return;
    var canvasHost = panel.querySelector('[data-qr-canvas]');
    drawQrPlaceholder(canvasHost, bar.getAttribute('data-verification-code'));
  }

  function handleSign(bar) {
    var panel = bar.querySelector('[data-sign-panel]');
    if (panel) {
      panel.hidden = !panel.hidden;
    }
  }

  function handleSignStub(bar) {
    var panel = bar.querySelector('[data-sign-panel]');
    if (!panel) return;
    var existing = panel.querySelector('.corp-sign-canvas');
    if (existing) return;
    var canvas = document.createElement('canvas');
    canvas.className = 'corp-sign-canvas';
    canvas.width = 400;
    canvas.height = 120;
    panel.appendChild(canvas);
    var ctx = canvas.getContext('2d');
    var drawing = false;
    function pos(e) {
      var rect = canvas.getBoundingClientRect();
      var clientX = e.touches ? e.touches[0].clientX : e.clientX;
      var clientY = e.touches ? e.touches[0].clientY : e.clientY;
      return { x: clientX - rect.left, y: clientY - rect.top };
    }
    function start(e) { drawing = true; var p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }
    function move(e) {
      if (!drawing) return;
      var p = pos(e);
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.strokeStyle = '#232323';
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      e.preventDefault();
    }
    function end() { drawing = false; }
    canvas.addEventListener('mousedown', start);
    canvas.addEventListener('mousemove', move);
    canvas.addEventListener('mouseup', end);
    canvas.addEventListener('mouseleave', end);
    canvas.addEventListener('touchstart', start, { passive: false });
    canvas.addEventListener('touchmove', move, { passive: false });
    canvas.addEventListener('touchend', end);
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    var bar = getBar(btn.closest('[data-report-actions]'));
    if (!bar) return;
    var action = btn.getAttribute('data-action');
    if (action === 'print') handlePrint();
    else if (action === 'excel') handleExcel(bar);
    else if (action === 'email') handleEmail(bar);
    else if (action === 'whatsapp') handleWhatsApp(bar);
    else if (action === 'qr') handleQr(bar);
    else if (action === 'sign') handleSign(bar);
    else if (action === 'sign-stub') handleSignStub(bar);
  });

  document.addEventListener('DOMContentLoaded', function () {
    if (window.location.search.indexOf('print=1') !== -1) {
      setTimeout(function () { window.print(); }, 400);
    }
  });
})();
