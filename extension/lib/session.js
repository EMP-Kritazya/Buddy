export const IDLE_SECONDS = 60; // 15 if I wanna test idle behavior
export const MIN_SESSION_MS = 2000;
export const HEARTBEAT_MINUTES = 0.5; // Chrome clamps alarms to a 30s floor
export const HEARTBEAT_MS = HEARTBEAT_MINUTES * 60 * 1000;
// How old a session must be before an alarm tick is allowed to report it.
//
// The alarm is a fixed metronome and does NOT restart when a session opens, so requiring a full
// HEARTBEAT_MS of session age meant a session beginning mid-cycle missed that tick and waited
// for the next one - 31 to 60 seconds before its first progress report, and nothing at all if
// it ended inside that window. Half the period puts the worst case back at one tick while still
// ignoring the sub-15s tab flicking the gate was written for.
export const MIN_BEAT_AGE_MS = HEARTBEAT_MS / 2;
// Three missed heartbeats means nobody was home: the machine slept or the worker was frozen.
export const SLEEP_GAP_MS = 3 * HEARTBEAT_MS;

export const RESUME_GAP_MS = 60 * 1000;

const REDACTED_DOMAINS = [];

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
    // Page identity, query string excluded: ?t=90 on a video, a tracking parameter or a
    // re-sorted table is the same page, and splitting on those produced a row per fiddle.
    // Switching to a different YouTube video changes the pathname, so that still splits.
    url_key: url.origin + url.pathname,
    title: redacted ? "[redacted]" : base.title,
  };
}

// Resuming is judged on what the classifier would see - the site and the title - rather than
// the exact URL. Two views the model cannot tell apart should not become two rows.
const contentKey = (x) => `${x.domain ?? ""}\n${x.title ?? ""}`;

export function canResume(lastClosed, target, at) {
  if (!lastClosed || !target?.tracked) return false;
  return (
    contentKey(lastClosed) === contentKey(target) &&
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
