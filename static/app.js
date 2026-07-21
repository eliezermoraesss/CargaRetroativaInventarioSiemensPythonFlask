/**
 * app.js — Lógica do dashboard de Carga Retroativa de Inventário Siemens.
 * SSE para progresso em tempo real · Controle de start/stop · Log dinâmico.
 */

// ── Estado local ─────────────────────────────────────────────────────────────
let evtSource = null;
let running = false;

// ── Utilitários ───────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

function fmtNum(n) {
  if (n === null || n === undefined || (n === 0 && !running)) return '—';
  return Number(n).toLocaleString('pt-BR');
}

function fmtElapsed(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

// ── Atualizar cards de métricas ───────────────────────────────────────────────
function updateMetrics(data) {
  $('metricTotal').textContent     = data.total      > 0 ? fmtNum(data.total)     : '—';
  $('metricProcessed').textContent = data.processed  > 0 ? fmtNum(data.processed) : (data.running ? '0' : '—');
  $('metricSuccess').textContent   = data.success    > 0 ? fmtNum(data.success)   : (data.running ? '0' : '—');
  $('metricErrors').textContent    = data.errors     > 0 ? fmtNum(data.errors)    : (data.running ? '0' : '—');
  $('metricBatches').textContent   = data.batches_total > 0
    ? `${fmtNum(data.batches_done)} / ${fmtNum(data.batches_total)}`
    : '—';
  $('metricElapsed').textContent   = data.elapsed_seconds > 0 ? fmtElapsed(data.elapsed_seconds) : '—';

  // Colorir erros
  $('cardErrors').style.borderColor = data.errors > 0 ? 'rgba(248,81,73,0.3)' : '';
}

// ── Barra de progresso ────────────────────────────────────────────────────────
function updateProgress(data) {
  const pct = data.percent || 0;
  $('progressBar').style.width  = pct + '%';
  $('progressGlow').style.width = pct + '%';
  $('progressPct').textContent  = pct + '%';
  $('progressTrack').setAttribute('aria-valuenow', pct);

  if (data.running) {
    const done    = data.processed || 0;
    const total   = data.total     || 0;
    const pending = total - done;
    $('progressDetails').textContent = total > 0
      ? `${fmtNum(done)} de ${fmtNum(total)} registros · ${fmtNum(pending)} pendentes`
      : 'Buscando registros de inventário no Oracle…';
  } else if (data.finished_at) {
    $('progressDetails').textContent = '✅ Carga de inventário finalizada.';
    $('progressEta').textContent = '';
  } else {
    $('progressDetails').textContent = 'Aguardando início…';
    $('progressEta').textContent = '';
  }
}

// ── Status global (pill no header) ───────────────────────────────────────────
function updateStatusPill(data) {
  const dot   = $('pillDot');
  const label = $('pillLabel');

  dot.className = 'pill-dot';
  if (data.running && data.stop_requested) {
    dot.classList.add('stopped');
    label.textContent = 'Parando…';
  } else if (data.running) {
    dot.classList.add('running');
    label.textContent = 'Em execução' + (data.dry_run ? ' (dry-run)' : '');
  } else if (data.finished_at) {
    if (data.errors > 0) {
      dot.classList.add('error');
      label.textContent = 'Concluído com erros';
    } else {
      dot.classList.add('done');
      label.textContent = 'Concluído';
    }
  } else {
    label.textContent = 'Aguardando';
  }
}

// ── Botões ────────────────────────────────────────────────────────────────────
function updateButtons(isRunning) {
  running = isRunning;
  $('btnStart').disabled  = isRunning;
  $('btnDryRun').disabled = isRunning;
  $('btnStop').disabled   = !isRunning;
}

// ── Log ───────────────────────────────────────────────────────────────────────
function appendLog(entry) {
  const logBody = $('logBody');

  const empty = logBody.querySelector('.log-empty');
  if (empty) empty.remove();

  const div   = document.createElement('div');
  div.className = 'log-entry';

  const time  = document.createElement('span');
  time.className   = 'log-time';
  time.textContent = entry.time || '';

  const level = document.createElement('span');
  level.className   = `log-level log-level--${entry.level}`;
  level.textContent = entry.level;

  const msg  = document.createElement('span');
  msg.className   = 'log-msg';
  msg.textContent = entry.message;

  div.appendChild(time);
  div.appendChild(level);
  div.appendChild(msg);
  logBody.appendChild(div);

  logBody.scrollTop = logBody.scrollHeight;

  const entries = logBody.querySelectorAll('.log-entry');
  if (entries.length > 300) entries[0].remove();
}

function clearLog() {
  $('logBody').innerHTML = '<div class="log-empty">Log limpo.</div>';
}

// ── Tabela de erros ───────────────────────────────────────────────────────────
function renderErrorTable(failedBatches) {
  if (!failedBatches || failedBatches.length === 0) {
    $('errorsSection').style.display = 'none';
    return;
  }
  $('errorsSection').style.display = '';
  const tbody = $('errTableBody');
  tbody.innerHTML = '';
  failedBatches.forEach((fb) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${fb.index}</td>
      <td>${fmtNum(fb.size)}</td>
      <td>${escHtml(fb.error || '—')}</td>
    `;
    tbody.appendChild(tr);
  });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Processar evento de progresso ─────────────────────────────────────────────
function handleProgress(data) {
  updateMetrics(data);
  updateProgress(data);
  updateStatusPill(data);
  updateButtons(data.running);
  if (data.failed_batches) renderErrorTable(data.failed_batches);
}

// ── SSE ───────────────────────────────────────────────────────────────────────
function connectSSE() {
  if (evtSource) evtSource.close();

  evtSource = new EventSource('/api/stream');

  evtSource.addEventListener('progress', (e) => {
    try { handleProgress(JSON.parse(e.data)); } catch (_) {}
  });

  evtSource.addEventListener('log', (e) => {
    try { appendLog(JSON.parse(e.data)); } catch (_) {}
  });

  evtSource.onopen = () => {
    const el = $('footerConn');
    el.textContent = '● SSE conectado';
    el.className = 'footer-version connected';
  };

  evtSource.onerror = () => {
    const el = $('footerConn');
    el.textContent = '● SSE desconectado — reconectando…';
    el.className = 'footer-version disconnected';
  };
}

// ── Ações do usuário ──────────────────────────────────────────────────────────
async function startProcess(dryRun = false) {
  try {
    $('btnStart').disabled  = true;
    $('btnDryRun').disabled = true;

    const sd = $('startDate') ? $('startDate').value : '';
    const ed = $('endDate') ? $('endDate').value : '';
    const toOracle = (iso) => {
      if (!iso) return null;
      const p = iso.split('-');
      if (p.length !== 3) return null;
      return `${p[2]}/${p[1]}/${p[0]}`;
    };

    const start_date = toOracle(sd);
    const end_date = toOracle(ed);

    if (sd && ed && new Date(sd) > new Date(ed)) {
      alert('Período inválido: a data inicial é posterior à final.');
      $('btnStart').disabled = false;
      $('btnDryRun').disabled = false;
      return;
    }

    const resp = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: dryRun, start_date: start_date, end_date: end_date }),
    });

    if (resp.status === 409) {
      alert('Um processo já está em execução.');
      $('btnStart').disabled  = false;
      $('btnDryRun').disabled = false;
      return;
    }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      alert('Erro ao iniciar: ' + (body.error || resp.status));
      $('btnStart').disabled  = false;
      $('btnDryRun').disabled = false;
    }
  } catch (err) {
    alert('Falha de comunicação com o servidor: ' + err.message);
    $('btnStart').disabled  = false;
    $('btnDryRun').disabled = false;
  }
}

async function stopProcess() {
  $('btnStop').disabled = true;
  try {
    await fetch('/api/stop', { method: 'POST' });
  } catch (err) {
    console.error('Falha ao parar:', err);
    $('btnStop').disabled = false;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
(async function init() {
  try {
    const resp = await fetch('/api/status');
    if (resp.ok) {
      const data = await resp.json();
      handleProgress(data);
      if (data.log && data.log.length > 0) {
        data.log.forEach(appendLog);
      }
    }
  } catch (_) {}

  try {
    const todayIso = new Date().toISOString().slice(0,10);
    if ($('endDate') && !$('endDate').value) $('endDate').value = todayIso;
    if ($('startDate') && !$('startDate').value) $('startDate').value = '2019-07-31';
  } catch (_) {}

  connectSSE();
})();
