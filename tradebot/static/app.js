const $ = (id) => document.getElementById(id);

const fmtMoney = (n) =>
  n == null ? '—' : '$' + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function refreshAccount() {
  try {
    const a = await api('/api/account');
    $('pv').textContent = fmtMoney(a.portfolio_value ?? a.equity ?? a.cash);
    $('cash').textContent = fmtMoney(a.cash);
    $('bp').textContent = fmtMoney(a.buying_power);
    $('acct-status').textContent = a.status || 'connected';
  } catch (e) {
    $('pv').textContent = '—';
    $('acct-status').textContent = e.message;
  }
}

async function refreshPositions() {
  const el = $('positions-list');
  try {
    const list = await api('/api/positions');
    if (!list.length) {
      el.innerHTML = '<div class="empty">no open positions</div>';
      return;
    }
    el.innerHTML = list
      .map(
        (p) => `
      <div class="position">
        <div>
          <div class="sym">${p.symbol}</div>
          <div class="qty">${Number(p.quantity).toFixed(4)} @ ${fmtMoney(p.avg_price)}</div>
        </div>
        <div class="value" style="font-size:16px">${fmtMoney(p.quantity * p.avg_price)}</div>
      </div>`,
      )
      .join('');
  } catch (e) {
    el.innerHTML = `<div class="empty">${e.message}</div>`;
  }
}

async function refreshEvents() {
  try {
    const events = await api('/api/events');
    $('events').innerHTML = events
      .map((e) => {
        const ts = new Date(e.ts * 1000).toLocaleTimeString();
        return `<li><span class="ts">${ts}</span><span class="lvl-${e.level}">${escapeHtml(e.message)}</span></li>`;
      })
      .join('');
  } catch {}
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

async function refreshStatus() {
  try {
    const s = await api('/api/status');
    const dot = $('bot-dot');
    const btn = $('toggle-bot');
    if (s.running) {
      dot.classList.add('running');
      btn.textContent = 'Stop bot';
      btn.classList.add('running');
    } else {
      dot.classList.remove('running');
      btn.textContent = 'Start bot';
      btn.classList.remove('running');
    }
    if (s.last_tick) {
      $('last-tick').textContent = 'last tick ' + new Date(s.last_tick * 1000).toLocaleTimeString();
    }
    // Hydrate config inputs the first time only.
    if (!refreshStatus._hydrated) {
      refreshStatus._hydrated = true;
      $('broker').value = s.config.broker;
      $('dry-run').checked = !!s.config.dry_run;
      $('poll').value = s.config.poll_interval;
      $('fast').value = s.config.strategy.fast;
      $('slow').value = s.config.strategy.slow;
      $('order-size').value = s.config.order_size_usd;
      $('lookback').value = s.config.lookback_days;
      $('symbols').value = (s.config.symbols || []).join(', ');
    }
  } catch {}
}

async function saveConfig() {
  const patch = {
    broker: $('broker').value,
    dry_run: $('dry-run').checked,
    poll_interval: Number($('poll').value),
    order_size_usd: Number($('order-size').value),
    lookback_days: Number($('lookback').value),
    symbols: $('symbols').value.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean),
    strategy: { fast: Number($('fast').value), slow: Number($('slow').value) },
  };
  try {
    await api('/api/config', { method: 'POST', body: patch });
    await refreshAccount();
    await refreshPositions();
  } catch (e) {
    alert('save failed: ' + e.message);
  }
}

async function toggleBot() {
  const s = await api('/api/status');
  const path = s.running ? '/api/bot/stop' : '/api/bot/start';
  await api(path, { method: 'POST' });
  refreshStatus();
}

async function tickNow() {
  const btn = $('tick-now');
  btn.disabled = true;
  try {
    await api('/api/tick', { method: 'POST' });
  } catch (e) {
    alert('tick failed: ' + e.message);
  } finally {
    btn.disabled = false;
    refreshAll();
  }
}

async function manualOrder(side) {
  const symbol = $('trade-symbol').value.trim().toUpperCase();
  if (!symbol) return alert('enter a symbol');
  const notional = Number($('trade-notional').value) || null;
  try {
    await api('/api/orders', {
      method: 'POST',
      body: { symbol, side, notional_usd: side === 'buy' ? notional : null },
    });
    refreshAll();
  } catch (e) {
    alert('order failed: ' + e.message);
  }
}

function refreshAll() {
  refreshStatus();
  refreshAccount();
  refreshPositions();
  refreshEvents();
}

$('refresh').onclick = refreshAll;
$('save-config').onclick = saveConfig;
$('toggle-bot').onclick = toggleBot;
$('tick-now').onclick = tickNow;
$('buy').onclick = () => manualOrder('buy');
$('sell').onclick = () => manualOrder('sell');
$('broker').onchange = saveConfig;

refreshAll();
setInterval(refreshStatus, 5000);
setInterval(refreshEvents, 5000);
setInterval(refreshAccount, 15000);
setInterval(refreshPositions, 15000);
