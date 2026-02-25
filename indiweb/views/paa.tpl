<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <title>PAA Live Monitor</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 1rem;
      /* Extra bottom padding so content stays above Safari bottom toolbar on iPhone */
      padding-bottom: calc(1rem + env(safe-area-inset-bottom, 0px) + 100px);
      font-family: system-ui, -apple-system, sans-serif;
      background: #1a1a2e;
      color: #eaeaea;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .status-bar {
      font-size: clamp(0.75rem, 2.5vw, 1rem);
      padding: 0.5rem 0;
      border-bottom: 1px solid #333;
      margin-bottom: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .status-dot {
      width: 0.6em;
      height: 0.6em;
      border-radius: 50%;
      display: inline-block;
      margin-right: 0.3em;
    }
    .status-dot.connected { background: #2ecc71; }
    .status-dot.disconnected { background: #e74c3c; }
    .error-grid {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr;
      grid-template-rows: auto auto auto;
      gap: 1rem;
      align-content: center;
    }
    @media (min-width: 600px) {
      .error-grid { grid-template-columns: repeat(3, 1fr); grid-template-rows: 1fr; }
    }
    .error-block {
      background: #16213e;
      border-radius: 0.5rem;
      padding: 1rem;
      text-align: center;
    }
    .error-label {
      font-size: clamp(0.9rem, 3vw, 1.1rem);
      color: #94a3b8;
      margin-bottom: 0.25rem;
    }
    .error-value {
      font-size: clamp(2rem, 8vw, 4rem);
      font-weight: 700;
      line-height: 1.2;
    }
    .error-value.good { color: #2ecc71; }
    .error-value.warning { color: #f1c40f; }
    .error-value.bad { color: #e74c3c; }
    .error-value.waiting { color: #94a3b8; }
    .error-arcsec {
      font-size: clamp(0.8rem, 2.5vw, 1rem);
      color: #94a3b8;
      margin-top: 0.25rem;
    }
    .target-input {
      margin-top: 1rem;
      padding-top: 1rem;
      border-top: 1px solid #333;
    }
    .target-input label {
      font-size: 0.9rem;
      margin-right: 0.5rem;
    }
    .target-input input {
      width: 4em;
      padding: 0.25rem 0.5rem;
      font-size: 1rem;
      background: #16213e;
      border: 1px solid #333;
      border-radius: 0.25rem;
      color: #eaeaea;
    }
    .back-link {
      display: inline-block;
      margin-top: 1rem;
      color: #60a5fa;
      text-decoration: none;
      font-size: 0.9rem;
    }
    .back-link:hover { text-decoration: underline; }
    .diagnostic-box {
      display: none;
      background: #3d1a1a;
      border: 1px solid #c0392b;
      border-radius: 0.5rem;
      padding: 1rem;
      margin-bottom: 1rem;
      font-size: clamp(0.9rem, 2.5vw, 1rem);
      color: #f8d7da;
      word-break: break-all;
    }
    .diagnostic-box.visible { display: block; }
  </style>
</head>
<body>
  <div class="diagnostic-box" id="diagnostic-box"></div>
  <div class="status-bar">
    <span id="conn-status">
      <span class="status-dot disconnected"></span>
      <span id="conn-text">Connecting...</span>
    </span>
    <span id="msg-text"></span>
    <span id="age-text"></span>
  </div>

  <div class="error-grid">
    <div class="error-block">
      <div class="error-label">Total</div>
      <div class="error-value waiting" id="total-value">—</div>
      <div class="error-arcsec" id="total-arcsec"></div>
    </div>
    <div class="error-block">
      <div class="error-label">Altitude</div>
      <div class="error-value waiting" id="alt-value">—</div>
      <div class="error-arcsec" id="alt-arcsec"></div>
    </div>
    <div class="error-block">
      <div class="error-label">Azimuth</div>
      <div class="error-value waiting" id="az-value">—</div>
      <div class="error-arcsec" id="az-arcsec"></div>
    </div>
  </div>

  <div class="target-input">
    <label for="accuracy-target">Accuracy target (arcsec):</label>
    <input type="number" id="accuracy-target" min="10" max="300" value="60">
  </div>

  <a href="/" class="back-link">← Back to INDI Web Manager</a>

  <script>
    (function() {
      const altEl = document.getElementById('alt-value');
      const azEl = document.getElementById('az-value');
      const totalEl = document.getElementById('total-value');
      const altArcsecEl = document.getElementById('alt-arcsec');
      const azArcsecEl = document.getElementById('az-arcsec');
      const totalArcsecEl = document.getElementById('total-arcsec');
      const connDot = document.querySelector('.status-dot');
      const connText = document.getElementById('conn-text');
      const msgText = document.getElementById('msg-text');
      const ageText = document.getElementById('age-text');
      const diagnosticBox = document.getElementById('diagnostic-box');
      const targetInput = document.getElementById('accuracy-target');

      const STORAGE_KEY = 'paa_accuracy_target';
      targetInput.value = localStorage.getItem(STORAGE_KEY) || '60';
      targetInput.addEventListener('change', function() {
        localStorage.setItem(STORAGE_KEY, targetInput.value);
        updateTotalColor(totalEl, parseFloat(totalEl.dataset.arcsec || 0));
      });

      function getTarget() { return parseFloat(targetInput.value) || 60; }

      function arrowFor(dir) {
        if (dir === 'up') return '\u2191';
        if (dir === 'down') return '\u2193';
        if (dir === 'left') return '\u2190';
        if (dir === 'right') return '\u2192';
        return '';
      }

      function updateTotalColor(el, totalArcsec) {
        const target = getTarget();
        el.classList.remove('good', 'warning', 'bad', 'waiting');
        if (totalArcsec === undefined || isNaN(totalArcsec)) {
          el.classList.add('waiting');
          return;
        }
        if (totalArcsec <= target) el.classList.add('good');
        else if (totalArcsec <= target * 2) el.classList.add('warning');
        else el.classList.add('bad');
      }

      function setConnectionState(connected) {
        connDot.className = 'status-dot ' + (connected ? 'connected' : 'disconnected');
        connText.textContent = connected ? 'Live' : 'Disconnected';
      }

      let ws = null;
      let reconnectDelay = 1000;
      let ageSeconds = 0;
      let ageInterval = null;

      function startAgeCounter() {
        if (ageInterval) clearInterval(ageInterval);
        ageSeconds = 0;
        ageText.textContent = '0s ago';
        ageInterval = setInterval(function() {
          ageSeconds++;
          ageText.textContent = ageSeconds + 's ago';
        }, 1000);
      }

      function stopAgeCounter() {
        if (ageInterval) {
          clearInterval(ageInterval);
          ageInterval = null;
        }
        ageText.textContent = '';
      }

      function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = protocol + '//' + window.location.host + '/ws/paa';
        ws = new WebSocket(wsUrl);

        ws.onopen = function() {
          setConnectionState(true);
          reconnectDelay = 1000;
        };

        ws.onclose = function() {
          setConnectionState(false);
          ws = null;
          setTimeout(connect, reconnectDelay);
          reconnectDelay = Math.min(reconnectDelay * 1.5, 30000);
        };

        ws.onerror = function() {};

        ws.onmessage = function(event) {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'heartbeat') {
              return;
            }
            if (data.type === 'update') {
              diagnosticBox.textContent = '';
              diagnosticBox.classList.remove('visible');
              const altArrow = arrowFor(data.alt_direction || '');
              const azArrow = arrowFor(data.az_direction || '');
              altEl.textContent = (altArrow ? altArrow + ' ' : '') + (data.alt || '—');
              azEl.textContent = (azArrow ? azArrow + ' ' : '') + (data.az || '—');
              totalEl.textContent = data.total || '—';
              totalEl.dataset.arcsec = data.total_arcsec != null ? String(data.total_arcsec) : '';
              altArcsecEl.textContent = '';
              azArcsecEl.textContent = '';
              totalArcsecEl.textContent = '';
              updateTotalColor(totalEl, data.total_arcsec);
              msgText.textContent = data.state === 'active' ? 'PAA active' : '';
              startAgeCounter();
            } else if (data.type === 'status') {
              if (data.state === 'waiting') {
                if (data.message && data.message !== 'Waiting for PAA data...') {
                  diagnosticBox.textContent = data.message;
                  diagnosticBox.classList.add('visible');
                  msgText.textContent = '';
                } else {
                  diagnosticBox.textContent = '';
                  diagnosticBox.classList.remove('visible');
                  msgText.textContent = data.message || '';
                }
                altEl.textContent = '—';
                azEl.textContent = '—';
                totalEl.textContent = '—';
                altArcsecEl.textContent = '';
                azArcsecEl.textContent = '';
                totalArcsecEl.textContent = '';
                totalEl.classList.remove('good', 'warning', 'bad');
                totalEl.classList.add('waiting');
                stopAgeCounter();
              } else {
                diagnosticBox.textContent = '';
                diagnosticBox.classList.remove('visible');
                msgText.textContent = data.message || '';
              }
              if (data.state === 'stale' && data.timestamp && data.total_arcsec != null) {
                const altArrow = arrowFor(data.alt_direction || '');
                const azArrow = arrowFor(data.az_direction || '');
                altEl.textContent = (altArrow ? altArrow + ' ' : '') + (data.alt || '—');
                azEl.textContent = (azArrow ? azArrow + ' ' : '') + (data.az || '—');
                totalEl.textContent = data.total || '—';
                totalEl.dataset.arcsec = String(data.total_arcsec);
                updateTotalColor(totalEl, data.total_arcsec);
              }
            }
          } catch (e) { console.warn('PAA WS parse error:', e); }
        };
      }

      connect();
    })();
  </script>
</body>
</html>
