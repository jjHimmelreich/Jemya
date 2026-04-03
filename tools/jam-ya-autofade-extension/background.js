'use strict';

/**
 * background.js — Jam-Ya Auto Fade service worker
 *
 * Owns three concerns:
 *   1. Token management  – stores Bearer token; supports Jam-ya OAuth and
 *                          user-provided Client ID + PKCE (standalone mode)
 *   2. Playback polling  – calls GET /v1/me/player every 3 s (2 s near end of track)
 *   3. Fade engine       – PUT /v1/me/player/volume on smooth equal-power curve
 *
 * Auth source:
 *   Jamya OAuth – user connects via jam-ya.com; content-jamya.js reads the
 *                 resulting token from localStorage and sends it here.
 */

// ── State ─────────────────────────────────────────────────────────────────────

const state = {
  // Token
  token:       null,   // Raw Bearer token for Spotify API calls
  tokenExpiry: 0,      // Unix ms — estimated expiry
  tokenSource: null,   // 'jamya' | 'pkce' | null
  tokenInfo:   null,   // Full token_info object (used for token refresh in both jamya and pkce modes)

  // User-provided credentials (standalone / PKCE mode)
  spotifyClientId:     null,

  // Playback (last known)
  trackId:     null,
  trackName:   null,
  artistName:  null,
  progressMs:  0,
  durationMs:  0,
  isPlaying:   false,
  volumePercent: 50,
  deviceName:  null,   // e.g., "Web Player (Chrome)", "iPhone"
  deviceType:  null,   // e.g., "Computer", "Smartphone", "Speaker"

  // Crossfade settings
  crossfadeEnabled:   true,
  fadeOutDuration:    2500, // ms — how long the fade-out lasts
  fadeInDuration:     4500, // ms — how long the fade-in lasts
  minVolume:          15,   // % — lowest volume during fade (never fully silent)
  fadeOutCurveName:   'scurve',  // 'linear' | 'logarithmic' | 'exponential' | 'scurve' | 'eqpower'
  fadeInCurveName:    'scurve',  // 'linear' | 'logarithmic' | 'exponential' | 'scurve' | 'eqpower'

  // Fade state
  preFadeVolume: 50,    // volume captured before fade-out started
  preFadeVolumeProtected: false, // true between fade-out end and fade-in read — blocks poll sync

  // Detached window tracking
  detachedWindowId: null, // ID of the detached player window, if open
  isFadingOut:   false,
  isFadingIn:    false,
  fadeInterval:  null,  // setInterval handle for the active fade step loop

  // Polling
  pollTimer:     null,
  pollIntervalMs: 3000,

  // Rate-limit
  rateLimitUntil: 0,
};

// ── Persistence ───────────────────────────────────────────────────────────────

const LOG = (...args) => console.log('[Jemya/bg]', ...args);
const WARN = (...args) => console.warn('[Jemya/bg]', ...args);

async function loadState() {
  const s = await chrome.storage.local.get([
    'token', 'tokenExpiry', 'tokenSource', 'tokenInfo',
    'spotifyClientId',
    'crossfadeEnabled', 'fadeOutDuration', 'fadeInDuration', 'minVolume',
    'fadeOutCurveName', 'fadeInCurveName', 'preFadeVolume',
  ]);
  if (s.token         !== undefined) state.token         = s.token;
  if (s.tokenExpiry   !== undefined) state.tokenExpiry   = s.tokenExpiry;
  if (s.tokenSource   !== undefined) state.tokenSource   = s.tokenSource;
  if (s.tokenInfo     !== undefined) state.tokenInfo     = s.tokenInfo;
  if (s.spotifyClientId     !== undefined) state.spotifyClientId     = s.spotifyClientId;
  if (s.crossfadeEnabled  !== undefined) state.crossfadeEnabled  = s.crossfadeEnabled;
  if (s.fadeOutDuration   !== undefined) state.fadeOutDuration   = s.fadeOutDuration;
  if (s.fadeInDuration    !== undefined) state.fadeInDuration    = s.fadeInDuration;
  if (s.minVolume         !== undefined) state.minVolume         = s.minVolume;
  if (s.fadeOutCurveName  !== undefined) state.fadeOutCurveName  = s.fadeOutCurveName;
  if (s.fadeInCurveName   !== undefined) state.fadeInCurveName   = s.fadeInCurveName;
  if (s.preFadeVolume     !== undefined) state.preFadeVolume     = s.preFadeVolume;
  LOG('📦 State loaded from storage — token:', state.token ? state.token.slice(0, 12) + '…' : 'none', '| source:', state.tokenSource);
}

async function persistToken() {
  await chrome.storage.local.set({
    token:        state.token,
    tokenExpiry:  state.tokenExpiry,
    tokenSource:  state.tokenSource,
    tokenInfo:    state.tokenInfo,
    preFadeVolume: state.preFadeVolume,
  });
}

async function persistSettings() {
  await chrome.storage.local.set({
    crossfadeEnabled: state.crossfadeEnabled,
    fadeOutDuration:  state.fadeOutDuration,
    fadeInDuration:   state.fadeInDuration,
    minVolume:        state.minVolume,
    fadeOutCurveName: state.fadeOutCurveName,
    fadeInCurveName:  state.fadeInCurveName,
  });
}

// ── Spotify API helper ────────────────────────────────────────────────────────

async function getValidToken() {
  const isAlive = state.token && Date.now() < state.tokenExpiry - 60_000;
  if (!isAlive) LOG('🔄 Token stale/missing — source:', state.tokenSource, '| expiry in:', Math.round((state.tokenExpiry - Date.now()) / 1000) + 's');
  if (isAlive) return state.token;

  // Try refreshing pkce token — pure PKCE needs only client_id (no secret)
  if (state.tokenSource === 'pkce' && state.tokenInfo?.refresh_token && state.spotifyClientId) {
    try {
      const body = new URLSearchParams({
        grant_type:    'refresh_token',
        refresh_token: state.tokenInfo.refresh_token,
        client_id:     state.spotifyClientId,
      });
      const res = await fetch('https://accounts.spotify.com/api/token', {
        method:  'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body:    body.toString(),
      });
      if (res.ok) {
        const data = await res.json();
        state.token       = data.access_token;
        state.tokenExpiry = Date.now() + (data.expires_in ?? 3600) * 1000;
        if (data.refresh_token) state.tokenInfo = { ...state.tokenInfo, refresh_token: data.refresh_token };
        await persistToken();
        LOG('✅ Token refreshed (pkce)');
        broadcast();
        return state.token;
      }
      WARN('❌ pkce token refresh failed:', res.status);
    } catch (e) { WARN('❌ pkce token refresh error:', e.message); }
  }

  // Try refreshing if token came from jam-ya.com backend (has refresh_token)
  if (state.tokenSource === 'jamya' && state.tokenInfo?.refresh_token) {
    try {
      const res = await fetch('https://jam-ya.com/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_info: state.tokenInfo }),
      });
      if (res.ok) {
        const data = await res.json();
        const ti = data.token_info;
        state.tokenInfo   = ti;
        state.token       = ti.access_token;
        state.tokenExpiry = (ti.expires_at ?? 0) * 1000;
        await persistToken();
        LOG('✅ Token refreshed via jam-ya.com');
        return state.token;
      } else {
        WARN('❌ jam-ya.com refresh failed:', res.status);
      }
    } catch (e) { WARN('❌ jam-ya.com refresh error:', e.message); }
  }

  return state.token;
}

async function spotifyFetch(method, path, body = null) {
  if (Date.now() < state.rateLimitUntil) {
    throw Object.assign(new Error('rate_limited'), { code: 429 });
  }

  const token = await getValidToken();
  if (!token) throw Object.assign(new Error('no_token'), { code: 0 });

  const opts = {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
  if (body !== null) opts.body = JSON.stringify(body);

  const res = await fetch(`https://api.spotify.com${path}`, opts);

  if (res.status === 429) {
    const retry = parseInt(res.headers.get('Retry-After') ?? '5', 10);
    state.rateLimitUntil = Date.now() + retry * 1000;
    WARN('⏱ Rate limited — pausing for', retry, 's');
    throw Object.assign(new Error('rate_limited'), { code: 429 });
  }

  if (res.status === 401) {
    WARN('🔒 401 Unauthorized — marking token stale, waiting for re-capture');
    state.token       = null;
    state.tokenExpiry = 0;
    await persistToken();
    throw Object.assign(new Error('unauthorized'), { code: 401 });
  }

  if (res.status === 204 || res.status === 202) return null; // success, no body
  if (!res.ok) throw Object.assign(new Error(`http_${res.status}`), { code: res.status });

  // Check if there's actually content to parse
  const contentType = res.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    // No JSON content, but request was successful
    return null;
  }

  try {
    return await res.json();
  } catch (e) {
    // JSON parse failed, but the request itself was successful
    LOG('⚠ Response was not valid JSON, treating as success:', e.message);
    return null;
  }
}

// ── Queue ─────────────────────────────────────────────────────────────────────

async function fetchQueue() {
  if (!state.token) {
    return [];
  }
  
  try {
    const data = await spotifyFetch('GET', '/v1/me/player/queue');
    // Return the queue array (currently_playing is separate in the API response)
    return data.queue || [];
  } catch (e) {
    LOG('\u26a0 Queue fetch failed:', e.message);
    return [];
  }
}
async function playQueueTrack(queueIndex) {
  if (!state.token) {
    throw new Error('Not authenticated');
  }
  
  // queueIndex is the position in the queue (0 = next track, 1 = second track, etc.)
  // To reach queue[0], skip once. To reach queue[N], skip (N+1) times
  const skipsNeeded = queueIndex + 1;
  
  cancelActiveFade();
  
  if (state.crossfadeEnabled) {
    // Fade out over fadeOutDuration ms, then skip to the track
    const fadeOutDur = state.fadeOutDuration;
    LOG(`🎵 Skipping to queue position ${queueIndex} (${skipsNeeded} skip${skipsNeeded > 1 ? 's' : ''}): fading out over ${fadeOutDur / 1000}s`);
    startFadeOut(fadeOutDur);
    
    // Wait for fade to complete
    await new Promise(resolve => setTimeout(resolve, fadeOutDur));
  } else {
    LOG(`🎵 Skipping to queue position ${queueIndex} (${skipsNeeded} skip${skipsNeeded > 1 ? 's' : ''})`);
  }
  
  // Skip to the track by calling next endpoint multiple times
  for (let i = 0; i < skipsNeeded; i++) {
    await spotifyFetch('POST', '/v1/me/player/next');
    LOG(`  ↪ Skip ${i + 1}/${skipsNeeded} completed`);
    // Delay between skips
    if (i < skipsNeeded - 1) {
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }
  
  LOG(`✓ Successfully skipped ${skipsNeeded} track${skipsNeeded > 1 ? 's' : ''}`);
  
  // Force poll to detect the new track and trigger fade-in
  forcePoll();
}
// ── Volume control ────────────────────────────────────────────────────────────

async function setVolume(vol) {
  const v = Math.max(state.minVolume, Math.min(100, Math.round(vol)));
  state.volumePercent = v;
  await spotifyFetch('PUT', `/v1/me/player/volume?volume_percent=${v}`);
}

// ── Fade engine ───────────────────────────────────────────────────────────────

/**
 * applyCurve(name, t) — normalised 0→1 output for position t ∈ [0,1].
 *
 *   'linear'      — constant rate
 *   'exponential' — slow start, fast finish  (t²)
 *   'logarithmic' — fast start, slow finish  (ln-based, perceptually natural)
 *   'scurve'      — zero slope at both ends  (smoothstep)
 *   'eqpower'     — equal-power sin          (gentle start, confident finish)
 *
 * Fade-out: vol = minV + (from − minV) × (1 − applyCurve(fadeOutCurveName, t))
 * Fade-in:  vol = minV + (to − minV)   ×       applyCurve(fadeInCurveName,  t)
 */
function applyCurve(name, t) {
  const c = Math.max(0, Math.min(1, t));
  switch (name) {
    case 'linear':      return c;
    case 'exponential': return c * c;
    case 'logarithmic': return Math.log(1 + c * (Math.E - 1));
    case 'eqpower':     return Math.sin(c * Math.PI * 0.5);
    default:            return c * c * (3 - 2 * c); // 'scurve'
  }
}

function cancelActiveFade() {
  if (state.fadeInterval) {
    clearInterval(state.fadeInterval);
    state.fadeInterval = null;
  }
  state.isFadingOut = false;
  state.isFadingIn  = false;
}

/**
 * Fade volume from current level to 0 over `durationMs` milliseconds.
 * Called when the track is approaching its end.
 */
function startFadeOut(durationMs) {
  if (state.isFadingOut || state.isFadingIn) return;

  LOG(`🔉 Fade-out starting: ${state.volumePercent}% → 1 over ${Math.round(durationMs / 1000 * 10) / 10}s`);
  const from = state.volumePercent;
  const stepMs = 250; // 4 writes/sec — Spotify rate limit is 1 call per 250ms
  const totalSteps = Math.max(1, Math.floor(durationMs / stepMs));
  let step = 0;

  state.preFadeVolume = from;
  state.preFadeVolumeProtected = true; // protect until startFadeIn reads it
  state.isFadingOut   = true;

  state.fadeInterval = setInterval(async () => {
    step++;
    const t   = step / totalSteps;
    // Fade from `from` down to minVolume
    const vol = state.minVolume + (from - state.minVolume) * (1 - applyCurve(state.fadeOutCurveName, t));
    try { await setVolume(vol); } catch (_) {}

    if (step >= totalSteps) {
      clearInterval(state.fadeInterval);
      state.fadeInterval = null;
      state.isFadingOut  = false;
    }
  }, stepMs);
}

/**
 * Fade volume from minVolume to the pre-fade level over fadeInDuration ms.
 * Called immediately after a new track is detected.
 */
function startFadeIn() {
  cancelActiveFade();

  const to         = state.preFadeVolume || state.volumePercent || 50;
  state.preFadeVolumeProtected = false; // safe to sync from API again after this read
  const durationMs = state.fadeInDuration;
  const stepMs     = 250; // 4 writes/sec — Spotify rate limit is 1 call per 250ms
  const totalSteps = Math.max(1, Math.floor(durationMs / stepMs));
  let step = 0;

  LOG(`🔊 Fade-in starting: 1 → ${to}% over ${durationMs / 1000}s (${totalSteps} steps)`);
  state.isFadingIn = true;

  // Start at minimum volume immediately
  setVolume(state.minVolume).catch(() => {});

  state.fadeInterval = setInterval(async () => {
    step++;
    const t   = step / totalSteps;
    // Fade from minVolume up to `to`
    const vol = state.minVolume + (to - state.minVolume) * applyCurve(state.fadeInCurveName, t);
    try { await setVolume(vol); } catch (_) {}

    if (step >= totalSteps) {
      clearInterval(state.fadeInterval);
      state.fadeInterval  = null;
      state.isFadingIn    = false;
      state.volumePercent = to;
      state.preFadeVolume = to;
      // Guarantee final volume is exact
      setVolume(to).catch(() => {});
    }
  }, stepMs);
}

// ── Playback polling ──────────────────────────────────────────────────────────

function schedulePoll() {
  state.pollTimer = setTimeout(() => {
    pollPlayback().finally(schedulePoll);
  }, state.pollIntervalMs);
}

function startPolling() {
  if (!state.pollTimer) schedulePoll();
}

/** Cancel the pending poll and run one immediately (used after transport commands). */
function forcePoll() {
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  state.pollIntervalMs = 2000; // stay slightly fast after skip
  schedulePoll();
}

async function pollPlayback() {
  if (!state.token) return; // silently skip — no token yet
  let data;
  try {
    data = await spotifyFetch('GET', '/v1/me/player');
  } catch (e) {
    WARN('⚠ Poll failed:', e.message);
    return;
  }

  // No active playback or no track
  if (!data || !data.item) {
    LOG('⏸ No active playback');
    return;
  }

  const prevTrackId = state.trackId;
  state.trackId    = data.item.id;
  state.trackName  = data.item.name;
  state.artistName = (data.item.artists ?? []).map((a) => a.name).join(', ');
  state.progressMs = data.progress_ms ?? 0;
  state.durationMs = data.item.duration_ms ?? 0;
  state.isPlaying  = data.is_playing ?? false;
  state.deviceName = data.device?.name ?? null;
  state.deviceType = data.device?.type ?? null;

  // Sync volume from API only when not actively writing it ourselves
  if (!state.isFadingOut && !state.isFadingIn) {
    const apiVol = data.device?.volume_percent;
    if (apiVol !== null && apiVol !== undefined) {
      state.volumePercent = apiVol;
      // Don't overwrite preFadeVolume while it's protected — it holds the
      // real user volume that startFadeIn needs to restore to.
      if (!state.preFadeVolumeProtected) state.preFadeVolume = apiVol;
    }
  }

  // ── Device eligibility check ─────────────────────────────────────────────
  // Only control Web Player devices (e.g., "Web Player (Chrome)", "Web Player (Firefox)")
  const isEligibleDevice = state.deviceName?.toLowerCase().includes('web player') ?? false;
  
  LOG(`🎵 "${state.trackName}" — ${Math.round(state.progressMs / 1000)}s / ${Math.round(state.durationMs / 1000)}s | device: ${state.deviceName} (${state.deviceType}) | vol: ${state.volumePercent}% | eligible: ${isEligibleDevice} | fading: ${state.isFadingOut ? 'out' : state.isFadingIn ? 'in' : 'no'}`);

  // Skip all control logic if device is not eligible
  if (!isEligibleDevice) {
    LOG('⏭ Skipping control — device not eligible per settings');
    broadcast();
    return;
  }

  // ── A new track started — always check even during fades ──────────────────
  // This is the ONLY way fade-in gets triggered for natural track advances.
  if (prevTrackId && prevTrackId !== state.trackId) {
    LOG('⏭ Track changed:', prevTrackId?.slice(0, 8), '→', state.trackId?.slice(0, 8));
    cancelActiveFade();
    if (state.crossfadeEnabled) startFadeIn();
    broadcast();
    return;
  }

  // ── Skip fade triggers while already fading ────────────────────────────────
  if (state.isFadingOut || state.isFadingIn) {
    broadcast();
    return;
  }

  // ── Approaching end of track — begin fade-out ─────────────────────────────
  // The trigger window is halfFade + one full poll interval, so a late-firing
  // poll never misses the window. The fade always runs for the full halfFade
  // duration regardless of when the poll actually fired within the window.
  const fadeOutDur = state.fadeOutDuration;
  const remaining  = state.durationMs - state.progressMs;
  if (state.crossfadeEnabled && state.isPlaying && !state.isFadingOut && !state.isFadingIn) {
    if (remaining > 200 && remaining <= fadeOutDur + state.pollIntervalMs) {
      LOG(`⏳ Fade window: ${Math.round(remaining / 1000 * 10) / 10}s remaining → fading out over ${fadeOutDur / 1000}s`);
      startFadeOut(fadeOutDur);
    }
  }

  // ── Adaptive poll rate: tighten up near the fade window ───────────────────
  const wantFast   = state.crossfadeEnabled && remaining <= fadeOutDur + 8000;
  state.pollIntervalMs = wantFast ? 1000 : 3000;
  broadcast();
}

// ── Icon state ───────────────────────────────────────────────────────────────

function updateIcon() {
  const connected = !!state.token && Date.now() < state.tokenExpiry + 120_000;
  chrome.action.setIcon({
    path: { 128: connected ? 'icons/icon-128.png' : 'icons/icon-128-off.png' },
  });
}

chrome.tabs.onActivated.addListener(() => updateIcon());
chrome.tabs.onUpdated.addListener((_tabId, info) => {
  if (info.status === 'complete') updateIcon();
});

// ── Alarms keepalive + poll heartbeat ─────────────────────────────────────────
// MV3 service workers die after ~30s of inactivity. setTimeout alone cannot
// prevent this. chrome.alarms guarantees periodic wakeup.

const ALARM_NAME = 'jemya-heartbeat';

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== ALARM_NAME) return;
  LOG('⏰ Heartbeat alarm — worker alive, poll running:', !!state.pollTimer);
  // Restart polling if the setTimeout loop died while the worker was suspended
  if (!state.pollTimer) {
    LOG('🔁 Restarting polling after worker suspension');
    startPolling();
  }
});

function ensureAlarm() {
  chrome.alarms.get(ALARM_NAME, (existing) => {
    if (!existing) {
      chrome.alarms.create(ALARM_NAME, { periodInMinutes: 0.4 }); // ~24s
      LOG('⏰ Heartbeat alarm created (24s)');
    }
  });
}

// ── Popup state broadcast ─────────────────────────────────────────────────────

function getPublicState() {
  return {
    hasToken:          !!state.token && Date.now() < state.tokenExpiry + 120_000,
    tokenSource:       state.tokenSource,
    trackId:           state.trackId,
    trackName:         state.trackName,
    artistName:        state.artistName,
    progressMs:        state.progressMs,
    durationMs:        state.durationMs,
    isPlaying:         state.isPlaying,
    volumePercent:     state.volumePercent,
    deviceName:        state.deviceName,
    deviceType:        state.deviceType,
    crossfadeEnabled: state.crossfadeEnabled,
    fadeOutDuration:  state.fadeOutDuration,
    fadeInDuration:   state.fadeInDuration,
    minVolume:        state.minVolume,
    fadeOutCurveName: state.fadeOutCurveName,
    fadeInCurveName:  state.fadeInCurveName,
    isFadingOut:      state.isFadingOut,
    isFadingIn:       state.isFadingIn,
    rateLimited:      Date.now() < state.rateLimitUntil,
    snapshotAt:        Date.now(),
  };
}

function broadcast() {
  updateIcon();
  chrome.runtime.sendMessage({ type: 'STATE_UPDATE', state: getPublicState() })
    .catch(() => {}); // popup may not be open — ignore
}

// ── Message handling ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  switch (msg.type) {

    case 'JAMYA_TOKEN':
      handleJamyaToken(msg.token, msg.tokenInfo);
      sendResponse({ ok: true });
      break;

    case 'GET_STATE':
      sendResponse(getPublicState());
      break;

    case 'CONTROL':
      handleControl(msg.action)
        .then(() => sendResponse({ ok: true }))
        .catch((e) => sendResponse({ ok: false, error: e.message }));
      return true; // async response

    case 'SET_SETTING':
      handleSetSetting(msg.key, msg.value);
      sendResponse({ ok: true });
      break;

    case 'SET_VOLUME':
      // Direct volume change from popup slider — cancel any active fade first
      cancelActiveFade();
      setVolume(msg.value)
        .then(() => { state.preFadeVolume = msg.value; sendResponse({ ok: true }); })
        .catch((e) => sendResponse({ ok: false, error: e.message }));
      return true; // async response

    case 'SEEK':
      spotifyFetch('PUT', `/v1/me/player/seek?position_ms=${Math.round(msg.positionMs)}`)
        .then(() => {
          state.progressMs = msg.positionMs;
          forcePoll();
          sendResponse({ ok: true });
        })
        .catch((e) => sendResponse({ ok: false, error: e.message }));
      return true; // async response

    case 'TEST_FADE':
      testFade();
      sendResponse({ ok: true });
      break;

    case 'START_OAUTH':
      startOAuthFlow(sendResponse, msg.mode ?? 'jamya', msg.clientId);
      return true; // async response

    case 'SET_CREDENTIALS':
      state.spotifyClientId     = msg.clientId     || null;
      chrome.storage.local.set({
        spotifyClientId:     state.spotifyClientId,
      });
      LOG('🔑 Credentials updated — clientId:', state.spotifyClientId?.slice(0, 8) + '…');
      sendResponse({ ok: true });
      break;

    case 'LOGOUT':
      state.token       = null;
      state.tokenExpiry = 0;
      state.tokenSource = null;
      state.tokenInfo   = null;
      persistToken()
        .then(() => {
          LOG('👋 Logged out — token cleared');
          broadcast();
          sendResponse({ ok: true });
        });
      return true; // async response

    case 'DETACH_WINDOW':
      handleDetachWindow()
        .then((windowId) => sendResponse({ ok: true, windowId }))
        .catch((e) => sendResponse({ ok: false, error: e.message }));
      return true; // async response

    case 'FETCH_QUEUE':
      fetchQueue()
        .then((queue) => sendResponse({ ok: true, queue }))
        .catch((e) => sendResponse({ ok: false, error: e.message }));
      return true; // async response

    case 'PLAY_QUEUE_TRACK':
      playQueueTrack(msg.queueIndex)
        .then(() => sendResponse({ ok: true }))
        .catch((e) => sendResponse({ ok: false, error: e.message }));
      return true; // async response
  }
});

// Keepalive port from content-bridge.js — having this open prevents the
// service worker from sleeping while a Spotify Web Player tab is open.
chrome.runtime.onConnect.addListener((_port) => {
  // Intentionally empty — just holding the port open is enough.
});

// ── Detached window management ────────────────────────────────────────────────

async function handleDetachWindow() {
  // If a detached window already exists, focus it instead of creating a new one
  if (state.detachedWindowId !== null) {
    try {
      await chrome.windows.update(state.detachedWindowId, { focused: true });
      LOG('🪟 Focused existing detached window:', state.detachedWindowId);
      return state.detachedWindowId;
    } catch (e) {
      // Window was closed or doesn't exist anymore
      LOG('🪟 Detached window no longer exists, creating new one');
      state.detachedWindowId = null;
    }
  }

  // Create a new detached window
  const win = await chrome.windows.create({
    url: 'popup.html',
    type: 'popup',
    width: 320,
    height: 900,
    focused: true
  });
  
  state.detachedWindowId = win.id;
  LOG('🪟 Created detached window:', win.id);
  return win.id;
}

// Track window removal to clear detached window ID
chrome.windows.onRemoved.addListener((windowId) => {
  if (windowId === state.detachedWindowId) {
    state.detachedWindowId = null;
    LOG('🪟 Detached window closed');
  }
});

// ── Token handlers ────────────────────────────────────────────────────────────

function handleJamyaToken(token, tokenInfo) {
  if (!token) return;

  state.token       = token;
  state.tokenInfo   = tokenInfo ?? null;
  state.tokenExpiry = tokenInfo?.expires_at
    ? tokenInfo.expires_at * 1000
    : Date.now() + 3_600_000;
  state.tokenSource = 'jamya';

  LOG('🔑 Token stored (jamya):', token.slice(0, 12) + '…');
  persistToken();
  startPolling();
  updateIcon();
  broadcast();
}

// ── Transport controls ────────────────────────────────────────────────────────

async function handleControl(action) {
  switch (action) {
    case 'play':
      await spotifyFetch('PUT', '/v1/me/player/play');
      break;
    case 'pause':
      await spotifyFetch('PUT', '/v1/me/player/pause');
      break;
    case 'next':
      cancelActiveFade();
      if (state.crossfadeEnabled) {
        // Fade out over fadeOutDuration ms, then skip — no seeking needed.
        // Poll detects the new track and triggers fade-in automatically.
        const fadeOutDur = state.fadeOutDuration;
        LOG(`⏭ Manual next: fading out over ${fadeOutDur / 1000}s then skipping`);
        startFadeOut(fadeOutDur);
        setTimeout(() => {
          spotifyFetch('POST', '/v1/me/player/next').catch(() => {});
          forcePoll();
        }, fadeOutDur);
      } else {
        await spotifyFetch('POST', '/v1/me/player/next');
        forcePoll();
      }
      break;
    case 'prev':
      cancelActiveFade();
      if (state.crossfadeEnabled) {
        // Fade out over fadeOutDuration ms, then skip back.
        const fadeOutDur = state.fadeOutDuration;
        LOG(`⏮ Manual prev: fading out over ${fadeOutDur / 1000}s then skipping back`);
        startFadeOut(fadeOutDur);
        setTimeout(() => {
          spotifyFetch('POST', '/v1/me/player/previous').catch(() => {});
          forcePoll();
        }, fadeOutDur);
      } else {
        await spotifyFetch('POST', '/v1/me/player/previous');
        forcePoll();
      }
      break;
  }
}

// ── Settings ──────────────────────────────────────────────────────────────────

/** Triggered by popup's Test-fade button — fade out then fade in without skipping. */
let testFadeActive = false;

function testFade() {
  // Second press while running cancels and restores volume.
  if (state.isFadingOut || state.isFadingIn) {
    testFadeActive = false; // prevent pending setTimeout from starting fade-in
    const restore = state.preFadeVolume || state.volumePercent;
    cancelActiveFade();
    setVolume(restore).catch(() => {});
    broadcast();
    return;
  }
  if (!state.token) return; // need a token to write volume
  LOG('🧪 Test fade — out:', state.fadeOutDuration / 1000 + 's, in:', state.fadeInDuration / 1000 + 's');
  testFadeActive = true;
  startFadeOut(state.fadeOutDuration);
  // Wait for fade-out to finish (plus 500ms so the last async setVolume call can settle)
  // then start fade-in only if the test wasn't cancelled mid-way.
  setTimeout(() => {
    if (testFadeActive) {
      testFadeActive = false;
      startFadeIn();
    }
  }, state.fadeOutDuration + 500);
}

function handleSetSetting(key, value) {
  if (key === 'crossfadeEnabled') state.crossfadeEnabled = !!value;
  if (key === 'fadeOutDuration')  state.fadeOutDuration  = Number(value);
  if (key === 'fadeInDuration')   state.fadeInDuration   = Number(value);
  if (key === 'minVolume')        state.minVolume        = Number(value);
  if (key === 'fadeOutCurveName') state.fadeOutCurveName = String(value);
  if (key === 'fadeInCurveName')  state.fadeInCurveName  = String(value);
  persistSettings();
  broadcast();
}

// ── PKCE helpers ─────────────────────────────────────────────────────────────

function generateCodeVerifier() {
  const arr = new Uint8Array(48);
  crypto.getRandomValues(arr);
  return btoa(String.fromCharCode(...arr))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

async function generateCodeChallenge(verifier) {
  const data    = new TextEncoder().encode(verifier);
  const digest  = await crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

// ── OAuth flow ────────────────────────────────────────────────────────────────
// Two modes:
//   Standalone: user provided their own Client ID. Uses real PKCE (no secret)
//               via chrome.identity.launchWebAuthFlow.
//   Jam-ya:     open a tab to jam-ya.com/callback; content-jamya.js picks
//               up the stored token and forwards it via JAMYA_TOKEN.

const SPOTIFY_CLIENT_ID = '535ef4e171b74750836388e73b3c20d7';
const SPOTIFY_REDIRECT  = 'https://jam-ya.com/callback';
const SPOTIFY_SCOPE     = 'user-read-playback-state user-modify-playback-state';

function startOAuthFlow(sendResponse, mode, providedClientId) {  // mode: 'pkce' | 'jamya'
  // Use provided clientId from popup (even if not saved yet) or fall back to saved one
  const clientId = providedClientId || state.spotifyClientId;
  if (mode === 'pkce' && clientId) {
    // ── Standalone / pure-PKCE mode ──────────────────────────────────────────
    const redirectUri = chrome.identity.getRedirectURL();
    const verifier    = generateCodeVerifier();

    generateCodeChallenge(verifier).then(challenge => {
      const params = new URLSearchParams({
        client_id:             clientId,
        response_type:         'code',
        redirect_uri:          redirectUri,
        scope:                 SPOTIFY_SCOPE,
        code_challenge_method: 'S256',
        code_challenge:        challenge,
      });
      const authUrl = `https://accounts.spotify.com/authorize?${params}`;

      chrome.identity.launchWebAuthFlow({ url: authUrl, interactive: true }, async (responseUrl) => {
        if (chrome.runtime.lastError || !responseUrl) {
          const msg = chrome.runtime.lastError?.message || 'OAuth cancelled';
          WARN('⚠ OAuth cancelled or failed:', msg);
          sendResponse?.({ ok: false, error: msg });
          return;
        }
        const url  = new URL(responseUrl);
        const code = url.searchParams.get('code');
        if (!code) {
          WARN('⚠ No code in OAuth redirect:', responseUrl);
          sendResponse?.({ ok: false, error: 'No authorisation code returned' });
          return;
        }
        // Exchange code using PKCE verifier — no client_secret needed
        try {
          const body = new URLSearchParams({
            grant_type:    'authorization_code',
            code,
            redirect_uri:  redirectUri,
            client_id:     clientId,
            code_verifier: verifier,
          });
          const res = await fetch('https://accounts.spotify.com/api/token', {
            method:  'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body:    body.toString(),
          });
          if (!res.ok) {
            const err = await res.text();
            WARN('⚠ Token exchange failed:', res.status, err);
            sendResponse?.({ ok: false, error: `Token exchange failed (${res.status})` });
            return;
          }
          const data = await res.json();
          state.token       = data.access_token;
          state.tokenExpiry = Date.now() + (data.expires_in ?? 3600) * 1000;
          state.tokenSource = 'pkce';
          state.tokenInfo   = data.refresh_token ? { refresh_token: data.refresh_token } : null;
          LOG('🔑 Token stored (pkce):', state.token.slice(0, 12) + '…');
          persistToken();
          startPolling();
          updateIcon();
          broadcast();
          sendResponse?.({ ok: true });
        } catch (e) {
          WARN('⚠ Token exchange error:', e.message);
          sendResponse?.({ ok: false, error: e.message });
        }
      });
    });
    return; // async
  } else {
    // ── Jam-ya mode ──────────────────────────────────────────────────────────
    const params = new URLSearchParams({
      client_id:     SPOTIFY_CLIENT_ID,
      response_type: 'code',
      redirect_uri:  SPOTIFY_REDIRECT,
      scope:         SPOTIFY_SCOPE,
    });
    chrome.tabs.create({ url: `https://accounts.spotify.com/authorize?${params}` });
    sendResponse?.({ ok: true });
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(async () => {
  // Set sensible defaults on first install
  const existing = await chrome.storage.local.get(['fadeOutDuration', 'fadeInDuration', 'minVolume', 'fadeOutCurveName', 'fadeInCurveName']);
  const defaults = {};
  if (existing.fadeOutDuration  === undefined) defaults.fadeOutDuration  = 5000;
  if (existing.fadeInDuration   === undefined) defaults.fadeInDuration   = 5000;
  if (existing.minVolume        === undefined) defaults.minVolume        = 3;
  if (existing.fadeOutCurveName === undefined) defaults.fadeOutCurveName = 'scurve';
  if (existing.fadeInCurveName  === undefined) defaults.fadeInCurveName  = 'scurve';
  if (Object.keys(defaults).length) await chrome.storage.local.set(defaults);
});

// Service worker entry point — runs every time the worker starts or is woken up
(async () => {
  LOG('🚀 Service worker started');
  await loadState();
  ensureAlarm();
  updateIcon();
  startPolling();
  LOG('⏰ Polling started');
})();
