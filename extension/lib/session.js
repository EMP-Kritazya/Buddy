// Session helpers: what counts as trackable, and the record shape sent to the backend.

export const IDLE_SECONDS = 60; // 15 if I wanna test idle behavior
export const MIN_SESSION_MS = 2000;
export const HEARTBEAT_MINUTES = 0.5; // Chrome clamps alarms to a 30s floor
export const HEARTBEAT_MS = HEARTBEAT_MINUTES * 60 * 1000;
// Three missed heartbeats means nobody was home: the machine slept or the worker was frozen.
export const SLEEP_GAP_MS = 3 * HEARTBEAT_MS;

// Titles on these domains (and their subdomains) never leave the machine, e.g. 'chase.com'.
const REDACTED_DOMAINS = [];

// Brands look like [{brand:'Google Chrome'}, {brand:'Chromium'}, {brand:'Not)A;Brand'}];
// pick the real product so Edge/Brave report themselves.
const BROWSER_NAME = detectBrowser();
function detectBrowser() {
  const named = (globalThis.navigator?.userAgentData?.brands ?? [])
    .map((b) => b.brand)
    .find((b) => !/chromium|not.?a.?brand/i.test(b));
  if (named) return named; // Chrome, Edge and Brave all name themselves here
  const ua = globalThis.navigator?.userAgent ?? "";
  const match = [
    [/Edg\//, "Microsoft Edge"],
    [/OPR\//, "Opera"],
    [/Chrome\//, "Google Chrome"],
  ].find(([re]) => re.test(ua));
  return match?.[1] ?? "Chromium";
}

// Sites put an unread count in the title ("(5504) YouTube"). It changes every few seconds and
// means nothing to the classifier, so it never enters the log.
const cleanTitle = (t) => (t ?? "").replace(/^\(\d+\)\s*/, "").trim();

export function describeTab(tab) {
  const base = {
    tab_id: tab.id,
    window_id: tab.windowId,
    title: cleanTitle(tab.title),
    audible: !!tab.audible,
  };
  let url;
  try {
    url = new URL(tab.url || tab.pendingUrl || "");
  } catch {
    return { ...base, tracked: false, url_key: "" };
  }
  // chrome://, new tab, extensions, file:// and incognito are never logged.
  if (tab.incognito || !["http:", "https:"].includes(url.protocol)) {
    return { ...base, tracked: false, url_key: url.href };
  }
  const domain = url.hostname.toLowerCase().replace(/^www\./, "");
  const redacted = REDACTED_DOMAINS.some(
    (d) => domain === d || domain.endsWith(`.${d}`),
  );
  return {
    ...base,
    tracked: true,
    domain,
    url_path: url.pathname,
    // Includes the query so e.g. switching YouTube videos starts a new session; stays local,
    // only url_path is ever sent.
    url_key: url.origin + url.pathname + url.search,
    title: redacted ? "[redacted]" : base.title,
  };
}

// Coming back to the same page after a short detour (an untracked tab, a glance at the
// terminal) continues the session it left instead of fragmenting one stay into several rows.
// Only the most recently closed session is eligible, so time spent on another tracked page can
// never be absorbed into this one - the worst case is up to RESUME_GAP_MS of untracked time.
export const RESUME_GAP_MS = 15 * 1000;

export function canResume(lastClosed, target, at) {
  if (!lastClosed || !target?.tracked) return false;
  return (
    lastClosed.url_key === target.url_key &&
    at - lastClosed.closed_at <= RESUME_GAP_MS
  );
}

export function resumeSession(lastClosed, target, at) {
  const { closed_at, ...session } = lastClosed;
  return {
    ...session, // keeps session_id, start_ms, beats and last_beat_end_ms
    tab_id: target.tab_id,
    window_id: target.window_id,
    title: target.title || session.title,
    audible: session.audible || target.audible,
    last_seen_ms: at,
  };
}

export function sameContent(session, target) {
  return session.tab_id === target.tab_id && session.url_key === target.url_key;
}

export function openSession(target, at) {
  return {
    session_id: crypto.randomUUID(),
    start_ms: at,
    last_seen_ms: at,
    beats: 0,
    last_beat_end_ms: 0,
    tab_id: target.tab_id,
    window_id: target.window_id,
    domain: target.domain,
    url_path: target.url_path,
    url_key: target.url_key,
    title: target.title,
    audible: target.audible,
  };
}

export async function toRecord(session, endMs, endReason, isFinal) {
  return {
    session_id: session.session_id,
    start_ts: new Date(session.start_ms).toISOString(),
    end_ts: new Date(endMs).toISOString(),
    duration_s: Math.round(endMs - session.start_ms) / 1000,
    app_name: BROWSER_NAME,
    app_type: "browser",
    browser_name: BROWSER_NAME,
    tab_id: session.tab_id,
    domain: session.domain,
    title: session.title,
    url_path: session.url_path,
    end_reason: endReason,
    is_final: isFinal,
    audible: session.audible,
    tz_offset_min: -new Date(session.start_ms).getTimezoneOffset(),
    client: {
      ext_version: chrome.runtime.getManifest().version,
      device_id: await deviceId(),
    },
  };
}

let cachedDeviceId;
async function deviceId() {
  if (cachedDeviceId) return cachedDeviceId;
  const { deviceId: stored } = await chrome.storage.local.get("deviceId");
  cachedDeviceId = stored ?? crypto.randomUUID();
  if (!stored) await chrome.storage.local.set({ deviceId: cachedDeviceId });
  return cachedDeviceId;
}
