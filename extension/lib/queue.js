// Outbound queue: records wait in storage.local until the ingest API acknowledges them, so
// nothing is lost while the backend is down or the browser restarts.

const INGEST_URL = 'http://127.0.0.1:8000/ingest';
const BATCH_SIZE = 200;
const MAX_QUEUE = 5000;
const MIN_BACKOFF_MS = 30 * 1000;
const MAX_BACKOFF_MS = 2 * 60 * 1000;

// Queue mutations get their own lock. flush() waits on the network outside of it, so a slow
// backend never delays event handling.
let chain = Promise.resolve();
function locked(task) {
  const result = chain.then(task);
  chain = result.catch(() => {});
  return result;
}

const recordKey = (r) => `${r.session_id}|${r.end_ts}|${r.is_final}`;

export function enqueue(record) {
  return locked(async () => {
    const { queue = [] } = await chrome.storage.local.get('queue');
    // A newer snapshot of a session supersedes any unsent older one (heartbeat → final).
    const next = queue.filter((r) => r.session_id !== record.session_id);
    next.push(record);
    await chrome.storage.local.set({ queue: next.slice(-MAX_QUEUE) });
  });
}

let inFlight = null;
export function flush({ force = false } = {}) {
  inFlight ??= send(force)
    .catch((err) => ({ ok: false, error: String(err) }))
    .finally(() => (inFlight = null));
  return inFlight;
}

async function send(force) {
  const { queue = [], flushStatus = {} } = await chrome.storage.local.get(['queue', 'flushStatus']);
  if (!queue.length) return flushStatus;
  if (!force && Date.now() < (flushStatus.retryAt ?? 0)) return flushStatus;

  const batch = queue.slice(0, BATCH_SIZE);
  let status;
  try {
    const res = await fetch(INGEST_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records: batch }),
      signal: AbortSignal.timeout(10_000),
    });
    if (res.ok) {
      await removeFromQueue(batch);
      status = { ok: true, at: Date.now(), sent: batch.length };
    } else if (res.status >= 400 && res.status < 500 && ![408, 429].includes(res.status)) {
      // The backend will never accept this batch (e.g. 422 after a schema change); retrying it
      // would block every record queued behind it forever.
      const detail = (await res.text()).slice(0, 300);
      console.warn('[buddy] dropping rejected batch', res.status, detail);
      await removeFromQueue(batch);
      status = { ok: false, at: Date.now(), dropped: batch.length, error: `HTTP ${res.status}, dropped ${batch.length} rejected records: ${detail}` };
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    const backoffMs = Math.min(Math.max((flushStatus.backoffMs ?? 0) * 2, MIN_BACKOFF_MS), MAX_BACKOFF_MS);
    status = { ok: false, at: Date.now(), error: err.message ?? String(err), backoffMs, retryAt: Date.now() + backoffMs };
  }
  await chrome.storage.local.set({ flushStatus: status });
  if (!status.retryAt && queue.length > BATCH_SIZE) return send(force);
  return status;
}

function removeFromQueue(batch) {
  const done = new Set(batch.map(recordKey));
  return locked(async () => {
    const { queue = [] } = await chrome.storage.local.get('queue');
    await chrome.storage.local.set({ queue: queue.filter((r) => !done.has(recordKey(r))) });
  });
}
