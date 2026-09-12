// Buddy activity capture: turns tab / window / idle events into focus sessions.
//
// Every event funnels into reconcile(), which asks "what is the user looking at right now?",
// compares it with the stored session, and closes/opens sessions accordingly. All state lives
// in chrome.storage because the MV3 service worker can be killed at any moment.

import {
  canResume,
  HEARTBEAT_MINUTES,
  HEARTBEAT_MS,
  IDLE_SECONDS,
  MIN_SESSION_MS,
  SLEEP_GAP_MS,
  describeTab,
  openSession,
  resumeSession,
  sameContent,
  toRecord,
} from "./lib/session.js";
import { enqueue, flush } from "./lib/queue.js";

const HEARTBEAT_ALARM = "buddy-heartbeat";
const FOCUS_DEBOUNCE_MS = 1000;
const WINDOW_NONE = chrome.windows.WINDOW_ID_NONE;

// onActivated, onFocusChanged and onUpdated often fire together; running them one at a time
// keeps the read-modify-write of the stored session from interleaving.
let chain = Promise.resolve();
function run(task) {
  chain = chain
    .then(async () => {
      await recoverIfNewRun();
      await task();
    })
    .catch((err) => console.error("[buddy]", err));
  return chain;
}

// Timestamp at event time, so a busy chain doesn't skew durations.
function trigger(update) {
  const at = Date.now();
  return run(async () => {
    if (update) await chrome.storage.local.set(update);
    await reconcile(at);
  }).then(() => flush());
}

// ---- event wiring (must be registered synchronously at top level) ----

chrome.idle.setDetectionInterval(IDLE_SECONDS);

chrome.runtime.onStartup.addListener(() => trigger());
chrome.runtime.onInstalled.addListener(() => trigger());

chrome.tabs.onActivated.addListener(() => trigger());
chrome.tabs.onCreated.addListener(() => trigger());
chrome.tabs.onRemoved.addListener(() => trigger());
chrome.tabs.onUpdated.addListener((_tabId, change, tab) => {
  if (!tab.active) return;
  if (change.url || change.title || "audible" in change) trigger();
});

// The popup holds a port open; its own focus blip shouldn't end the session it is displaying.
let popupPorts = 0;
chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "popup") return;
  popupPorts += 1;
  port.onDisconnect.addListener(() => (popupPorts -= 1));
});

let focusSeq = 0;
chrome.windows.onFocusChanged.addListener(
  (windowId) => {
    const seq = ++focusSeq;
    if (windowId !== WINDOW_NONE) {
      trigger({ focusedWindowId: windowId });
      return;
    }
    // macOS briefly reports NONE when a popup or devtools takes focus; only believe it if no
    // other window gained focus within the debounce window.
    const at = Date.now();
    setTimeout(() => {
      if (seq !== focusSeq || popupPorts > 0) return;
      run(async () => {
        await chrome.storage.local.set({ focusedWindowId: WINDOW_NONE });
        await reconcile(at);
      }).then(() => flush());
    }, FOCUS_DEBOUNCE_MS);
  },
  { windowTypes: ["normal"] },
);

chrome.idle.onStateChanged.addListener((idleState) => trigger({ idleState }));

chrome.alarms.get(HEARTBEAT_ALARM).then((alarm) => {
  // Re-creating an existing alarm resets its timer, which would starve it on frequent SW wakes.
  // A changed period still has to take effect, so recreate only when it no longer matches.
  if (alarm?.periodInMinutes !== HEARTBEAT_MINUTES) {
    chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: HEARTBEAT_MINUTES });
  }
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== HEARTBEAT_ALARM) return;
  const at = Date.now();
  run(() => heartbeat(at)).then(() => flush());
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "setPaused") {
    trigger({ paused: !!msg.paused }).then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg?.type === "flushNow") {
    flush({ force: true }).then(sendResponse);
    return true;
  }
});

// ---- session state machine ----

async function reconcile(at) {
  const st = await chrome.storage.local.get([
    "current",
    "focusedWindowId",
    "idleState",
    "paused",
  ]);
  let cur = st.current ?? null;

  // A silence longer than the heartbeat period means the machine slept: the session ended
  // when we last saw it, not now.
  if (cur && at - cur.last_seen_ms > SLEEP_GAP_MS) {
    await closeSession(cur, cur.last_seen_ms, "system_sleep");
    cur = null;
  }

  const tab = st.paused ? null : await activeTab(st.focusedWindowId);
  const away = st.paused
    ? "paused"
    : !tab
      ? "window_blur"
      : st.idleState === "locked"
        ? "locked"
        : st.idleState === "idle" && !tab.audible // a playing lecture/video isn't "away"
          ? "idle"
          : null;
  const target = away ? null : describeTab(tab);

  if (cur && target && sameContent(cur, target)) {
    // Late-loading titles and "(3) Inbox"-style changes update the session instead of splitting it.
    cur.title = target.title || cur.title;
    cur.audible ||= target.audible;
    cur.last_seen_ms = at;
    await chrome.storage.local.set({ current: cur });
    return;
  }

  if (cur) {
    const gone =
      cur.tab_id !== target?.tab_id && !(await tabExists(cur.tab_id));
    const reason = gone
      ? "tab_closed"
      : (away ?? (cur.tab_id !== target.tab_id ? "tab_switch" : "navigation"));
    // The idle event fires IDLE_SECONDS after the last input; that's when the user actually left.
    const endMs =
      reason === "idle" ? Math.max(cur.start_ms, at - IDLE_SECONDS * 1000) : at;
    const closedAt = await closeSession(cur, endMs, reason);
    // Remembered so a quick return to the same page continues this session rather than
    // starting a new one. Overwritten by the next close, so only the latest page can resume.
    await chrome.storage.local.set({ lastClosed: { ...cur, closed_at: closedAt } });
  }

  let next = null;
  if (target?.tracked) {
    const { lastClosed } = await chrome.storage.local.get("lastClosed");
    next = canResume(lastClosed, target, at)
      ? resumeSession(lastClosed, target, at)
      : openSession(target, at);
  }
  await chrome.storage.local.set({ current: next });
}

async function heartbeat(at) {
  await reconcile(at);
  const { current } = await chrome.storage.local.get("current");
  if (!current) return;
  // The alarm is a fixed metronome, but a progress report is only worth sending once per
  // interval of real session time. Opening a session - a tab switch, a navigation, a refresh -
  // starts that count over, so a 6-second-old session never reports.
  const sinceReported = at - Math.max(current.start_ms, current.last_beat_end_ms);
  if (sinceReported < HEARTBEAT_MS) return;
  // Non-final snapshot: the backend upserts on session_id, so long sessions are visible live.
  current.beats += 1;
  current.last_beat_end_ms = at;
  await chrome.storage.local.set({ current });
  await enqueue(await toRecord(current, at, "heartbeat", false));
}

async function closeSession(session, endMs, reason) {
  // A heartbeat already told the backend the session reached that point. Ending earlier (idle
  // backdates to the last input) would upsert a SHORTER row and retract time already reported.
  const end = Math.max(endMs, session.last_beat_end_ms ?? 0);
  // Sub-2s tab flicking is noise for the classifier, unless a heartbeat already reported it.
  const worthSending = end - session.start_ms >= MIN_SESSION_MS || session.beats;
  if (worthSending) await enqueue(await toRecord(session, end, reason, true));
  return end;
}

// storage.session is wiped when the browser (or the extension) restarts, so a missing marker
// means any stored session is left over from a previous run that ended without closing it.
async function recoverIfNewRun() {
  const { alive } = await chrome.storage.session.get("alive");
  if (alive) return;
  await chrome.storage.session.set({ alive: true });
  const { current } = await chrome.storage.local.get("current");
  if (current)
    await closeSession(current, current.last_seen_ms, "startup_recovery");
  await chrome.storage.local.set({
    current: null,
    lastClosed: null,
    focusedWindowId: null,
    idleState: await chrome.idle.queryState(IDLE_SECONDS),
  });
}

async function activeTab(focusedWindowId) {
  if (focusedWindowId === WINDOW_NONE) return null;
  if (focusedWindowId != null) {
    const [tab] = await chrome.tabs
      .query({ active: true, windowId: focusedWindowId })
      .catch(() => []);
    if (tab) return tab;
  }
  // Focus unknown (fresh start) or the remembered window was closed.
  const [tab] = await chrome.tabs.query({
    active: true,
    lastFocusedWindow: true,
  });
  return tab ?? null;
}

function tabExists(tabId) {
  return chrome.tabs.get(tabId).then(
    () => true,
    () => false,
  );
}
