// Debug view of the capture pipeline: current session, queue, last sync, pause toggle.

const $ = (id) => document.getElementById(id);

// Tells the background this popup is open, so the focus change it causes isn't logged as leaving.
chrome.runtime.connect({ name: 'popup' });

function formatDuration(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
  if (m) return `${m}m ${String(s % 60).padStart(2, '0')}s`;
  return `${s}s`;
}

let paused = false;

async function render() {
  const st = await chrome.storage.local.get(['current', 'queue', 'flushStatus', 'paused', 'idleState']);
  const cur = st.current;
  paused = !!st.paused;

  const state = $('state');
  if (paused) [state.textContent, state.className] = ['Paused', 'badge paused'];
  else if (cur) [state.textContent, state.className] = ['Tracking', 'badge tracking'];
  else if (st.idleState === 'idle' || st.idleState === 'locked') [state.textContent, state.className] = ['Idle', 'badge'];
  else [state.textContent, state.className] = ['Not tracking', 'badge'];

  $('domain').textContent = cur ? cur.domain + cur.url_path : 'No active session';
  $('title').textContent = cur?.title ?? '';
  $('elapsed').textContent = cur ? formatDuration(Date.now() - cur.start_ms) : '';

  $('queued').textContent = (st.queue ?? []).length;
  const fs = st.flushStatus;
  $('sync').textContent = fs?.at ? `${fs.ok ? 'ok' : 'failed'} · ${new Date(fs.at).toLocaleTimeString()}` : 'never';
  $('error').textContent = fs && !fs.ok ? fs.error : '';
  $('pause').textContent = paused ? 'Resume' : 'Pause';
}

$('pause').addEventListener('click', () => chrome.runtime.sendMessage({ type: 'setPaused', paused: !paused }));
$('flush').addEventListener('click', () => chrome.runtime.sendMessage({ type: 'flushNow' }));

chrome.storage.onChanged.addListener(render);
setInterval(render, 1000);
render();
