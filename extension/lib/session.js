// Session helpers: what counts as trackable, and the record shape sent to the backend.

export const IDLE_SECONDS = 60; // 15 if I wanna test idle behavior
export const MIN_SESSION_MS = 2000;
export const SLEEP_GAP_MS = 3 * 60 * 1000; // heartbeat is 1 min; 3 min of silence = machine slept

// Titles on these domains (and their subdomains) never leave the machine, e.g. 'chase.com'.
const REDACTED_DOMAINS = [];

// Brands look like [{brand:'Google Chrome'}, {brand:'Chromium'}, {brand:'Not)A;Brand'}];
// pick the real product so Edge/Brave report themselves.
const BROWSER_NAME =
  (globalThis.navigator?.userAgentData?.brands ?? [])
    .map((b) => b.brand)
    .find((b) => !/chromium|not.?a.?brand/i.test(b)) ?? 'Chromium';

export function describeTab(tab) {
  const base = {
    tab_id: tab.id,
    window_id: tab.windowId,
    title: tab.title ?? "",
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

export function sameContent(session, target) {
  return session.tab_id === target.tab_id && session.url_key === target.url_key;
}

export function openSession(target, at) {
  return {
    session_id: crypto.randomUUID(),
    start_ms: at,
    last_seen_ms: at,
    beats: 0,
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
    app_type: 'browser',
    browser_name: BROWSER_NAME,
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
