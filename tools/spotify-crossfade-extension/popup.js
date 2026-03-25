'use strict';

/**
 * popup.js — Jam-ya Spotify Auto Fade popup controller
 *
 * Requests current state from background on open, then listens for
 * STATE_UPDATE broadcasts. Extrapolates progress locally between updates.
 */

let lastState  = null;
let snapshotAt = Date.now();
let progressMs = 0;

// ── Messaging ─────────────────────────────────────────────────────────────────

function send(msg) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(msg, (res) => {
        if (chrome.runtime.lastError) { resolve(null); return; }
        resolve(res ?? null);
      });
    } catch (_) { resolve(null); }
  });
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'STATE_UPDATE') applyState(msg.state);
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(ms) {
  if (!ms || ms < 0) return '0:00';
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

// ── State → DOM ───────────────────────────────────────────────────────────────

function applyState(s) {
  lastState  = s;
  progressMs = s.progressMs;
  snapshotAt = s.snapshotAt ?? Date.now();
  render(s);
}

function render(s) {
  // Auth
  const authEl     = document.getElementById('authStatus');
  const connectBtn = document.getElementById('connectBtn');
  if (s.hasToken) {
    authEl.textContent = s.tokenSource === 'pkce'
      ? '✓ Custom App'
      : '✓ Jam-ya';
    authEl.className   = 'auth-status ok';
    connectBtn.style.display = 'none';
    document.getElementById('logoutBtn').style.display = 'inline-block';
  } else {
    authEl.textContent = 'Not connected';
    authEl.className   = 'auth-status err';
    connectBtn.style.display = 'inline-block';
    document.getElementById('logoutBtn').style.display = 'none';
  }

  // Track
  const trackEl  = document.getElementById('trackName');
  const artistEl = document.getElementById('artistName');
  if (s.trackName) {
    trackEl.textContent  = s.trackName;
    trackEl.className    = 'track-name';
    artistEl.textContent = s.artistName ?? '';
  } else {
    trackEl.textContent  = 'Nothing playing';
    trackEl.className    = 'track-name empty';
    artistEl.textContent = '';
  }

  document.getElementById('progressTotal').textContent = fmt(s.durationMs);
  document.getElementById('playPauseBtn').textContent  = s.isPlaying ? '⏸' : '▶';

  // Volume — don't clobber while user is dragging
  if (!volumeDragging) {
    const vol = s.volumePercent ?? 50;
    document.getElementById('volumeSlider').value = vol;
    document.getElementById('volumeValue').textContent = `${vol}%`;
  }

  // Settings
  document.getElementById('enableToggle')
    .classList.toggle('on', s.crossfadeEnabled);
  const fadeOut = s.fadeOutDuration ?? 5000;
  document.getElementById('fadeOutSlider').value = fadeOut;
  document.getElementById('fadeOutValue').textContent = `${(fadeOut / 1000).toFixed(1)}s`;
  const fadeIn = s.fadeInDuration ?? 5000;
  document.getElementById('fadeInSlider').value = fadeIn;
  document.getElementById('fadeInValue').textContent = `${(fadeIn / 1000).toFixed(1)}s`;
  const minVol = s.minVolume ?? 3;
  document.getElementById('minVolumeSlider').value = minVol;
  document.getElementById('minVolumeValue').textContent = `${minVol}%`;
  document.getElementById('fadeOutCurveSelect').value = s.fadeOutCurveName ?? 'scurve';
  document.getElementById('fadeInCurveSelect').value  = s.fadeInCurveName  ?? 'scurve';

  // Indicators — differentiated by fade phase
  const fadeBadge = document.getElementById('fadeBadge');
  if (s.isFadingOut) {
    fadeBadge.textContent = '↓ fading out…';
    fadeBadge.style.display = 'block';
  } else if (s.isFadingIn) {
    fadeBadge.textContent = '↑ fading in…';
    fadeBadge.style.display = 'block';
  } else {
    fadeBadge.style.display = 'none';
  }
  document.getElementById('rateWarning').style.display = s.rateLimited ? 'block' : 'none';

  // Test-fade button state
  const testBtn = document.getElementById('testFadeBtn');
  const isTesting = s.isFadingOut || s.isFadingIn;
  testBtn.textContent = isTesting ? '◼ Cancel' : '⏵ Test fade';
  testBtn.classList.toggle('testing', isTesting);

  drawCurves();
  updateProgress();
}

let seekDragging = false;

// Smooth progress bar between polls
function updateProgress() {
  if (seekDragging) return; // don't clobber while user is dragging
  if (!lastState?.durationMs) return;
  const elapsed = lastState.isPlaying ? (Date.now() - snapshotAt) : 0;
  const current = Math.min(progressMs + elapsed, lastState.durationMs);
  const pct     = (current / lastState.durationMs) * 100;
  document.getElementById('progressFill').style.width  = `${pct}%`;
  document.getElementById('progressCurrent').textContent = fmt(current);
}

setInterval(updateProgress, 500);

// ── Progress bar seek ────────────────────────────────────────────────────────

function pctFromEvent(e, bar) {
  const rect = bar.getBoundingClientRect();
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
}

const progressBar = document.getElementById('progressBar');

function onSeekStart(e) {
  if (!lastState?.durationMs) return;
  e.preventDefault();
  seekDragging = true;
  progressBar.classList.add('seeking');
  applySeekPreview(e);
  const moveEvt = e.type === 'touchstart' ? 'touchmove' : 'mousemove';
  const upEvt   = e.type === 'touchstart' ? 'touchend'  : 'mouseup';
  function onMove(e2) { applySeekPreview(e2); }
  function onUp(e2) {
    document.removeEventListener(moveEvt, onMove);
    document.removeEventListener(upEvt,   onUp);
    progressBar.classList.remove('seeking');
    seekDragging = false;
    const pct = pctFromEvent(e2.type === 'touchend' ? e2.changedTouches[0] : e2, progressBar);
    const posMs = Math.round(pct * lastState.durationMs);
    // Optimistically update local state so the bar doesn't jump back
    progressMs = posMs;
    snapshotAt = Date.now();
    send({ type: 'SEEK', positionMs: posMs });
  }
  document.addEventListener(moveEvt, onMove);
  document.addEventListener(upEvt,   onUp);
}

function applySeekPreview(e) {
  if (!lastState?.durationMs) return;
  const pct  = pctFromEvent(e, progressBar);
  const posMs = Math.round(pct * lastState.durationMs);
  document.getElementById('progressFill').style.width = `${pct * 100}%`;
  document.getElementById('progressCurrent').textContent = fmt(posMs);
}

progressBar.addEventListener('mousedown', onSeekStart);
progressBar.addEventListener('touchstart', onSeekStart, { passive: false });

// ── Curve visualizer ───────────────────────────────────────────────────────────────

// Mirror of applyCurve in background.js — kept in sync manually.
function applyPopupCurve(name, t) {
  const c = Math.max(0, Math.min(1, t));
  switch (name) {
    case 'linear':      return c;
    case 'exponential': return c * c;
    case 'logarithmic': return Math.log(1 + c * (Math.E - 1));
    case 'eqpower':     return Math.sin(c * Math.PI * 0.5);
    default:            return c * c * (3 - 2 * c); // 'scurve'
  }
}

function drawCurves() {
  const canvas = document.getElementById('curveCanvas');
  if (!canvas) return;
  const ctx    = canvas.getContext('2d');
  const W      = canvas.width;
  const H      = canvas.height;
  const minV   = (lastState?.minVolume ?? 3) / 100;
  const foMs   = lastState?.fadeOutDuration ?? 5000;
  const fiMs   = lastState?.fadeInDuration  ?? 5000;
  const foName = lastState?.fadeOutCurveName ?? 'scurve';
  const fiName = lastState?.fadeInCurveName  ?? 'scurve';
  const total  = foMs + fiMs;
  const xMid   = (foMs / total) * W;

  ctx.clearRect(0, 0, W, H);

  // Background
  ctx.fillStyle = 'rgba(0,0,0,0.3)';
  ctx.fillRect(0, 0, W, H);

  // Min-volume reference line
  const minY = H * (1 - minV);
  ctx.setLineDash([3, 4]);
  ctx.strokeStyle = 'rgba(255,255,255,0.11)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, minY); ctx.lineTo(W, minY); ctx.stroke();
  ctx.setLineDash([]);

  // Fade-out curve (red)
  ctx.strokeStyle = '#f87171';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let px = 0; px <= xMid; px++) {
    const t   = xMid > 0 ? px / xMid : 1;
    const vol = minV + (1 - minV) * (1 - applyPopupCurve(foName, t));
    const y   = H * (1 - vol);
    px === 0 ? ctx.moveTo(px, y) : ctx.lineTo(px, y);
  }
  ctx.stroke();

  // Fade-in curve (green)
  ctx.strokeStyle = '#34d399';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let px = Math.floor(xMid); px <= W; px++) {
    const span = W - xMid;
    const t    = span > 0 ? (px - xMid) / span : 1;
    const vol  = minV + (1 - minV) * applyPopupCurve(fiName, t);
    const y    = H * (1 - vol);
    px === Math.floor(xMid) ? ctx.moveTo(px, y) : ctx.lineTo(px, y);
  }
  ctx.stroke();

  // Vertical separator
  ctx.setLineDash([2, 3]);
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(xMid, 0); ctx.lineTo(xMid, H); ctx.stroke();
  ctx.setLineDash([]);
}

// ── Controls ──────────────────────────────────────────────────────────────────

let volumeDragging = false;

document.getElementById('playPauseBtn').addEventListener('click', () => {
  send({ type: 'CONTROL', action: lastState?.isPlaying ? 'pause' : 'play' });
});
document.getElementById('nextBtn').addEventListener('click', () => {
  send({ type: 'CONTROL', action: 'next' });
});
document.getElementById('prevBtn').addEventListener('click', () => {
  send({ type: 'CONTROL', action: 'prev' });
});
document.getElementById('enableToggle').addEventListener('click', () => {
  send({ type: 'SET_SETTING', key: 'crossfadeEnabled', value: !(lastState?.crossfadeEnabled ?? true) });
});
document.getElementById('fadeOutCurveSelect').addEventListener('change', (e) => {
  if (lastState) lastState.fadeOutCurveName = e.target.value;
  drawCurves();
  send({ type: 'SET_SETTING', key: 'fadeOutCurveName', value: e.target.value });
});
document.getElementById('fadeInCurveSelect').addEventListener('change', (e) => {
  if (lastState) lastState.fadeInCurveName = e.target.value;
  drawCurves();
  send({ type: 'SET_SETTING', key: 'fadeInCurveName', value: e.target.value });
});
document.getElementById('testFadeBtn').addEventListener('click', () => {
  send({ type: 'TEST_FADE' });
});
document.getElementById('fadeOutSlider').addEventListener('input', (e) => {
  const val = parseInt(e.target.value, 10);
  document.getElementById('fadeOutValue').textContent = `${(val / 1000).toFixed(1)}s`;
  if (lastState) lastState.fadeOutDuration = val;
  drawCurves();
  send({ type: 'SET_SETTING', key: 'fadeOutDuration', value: val });
});
document.getElementById('fadeInSlider').addEventListener('input', (e) => {
  const val = parseInt(e.target.value, 10);
  document.getElementById('fadeInValue').textContent = `${(val / 1000).toFixed(1)}s`;
  if (lastState) lastState.fadeInDuration = val;
  drawCurves();
  send({ type: 'SET_SETTING', key: 'fadeInDuration', value: val });
});
document.getElementById('minVolumeSlider').addEventListener('input', (e) => {
  const val = parseInt(e.target.value, 10);
  document.getElementById('minVolumeValue').textContent = `${val}%`;
  if (lastState) lastState.minVolume = val;
  drawCurves();
  send({ type: 'SET_SETTING', key: 'minVolume', value: val });
});
document.getElementById('volumeSlider').addEventListener('mousedown', () => { volumeDragging = true; });
document.getElementById('volumeSlider').addEventListener('touchstart', () => { volumeDragging = true; });
document.getElementById('volumeSlider').addEventListener('change', (e) => {
  volumeDragging = false;
  const val = parseInt(e.target.value, 10);
  document.getElementById('volumeValue').textContent = `${val}%`;
  send({ type: 'SET_VOLUME', value: val });
});
document.getElementById('connectBtn').addEventListener('click', async () => {
  const btn      = document.getElementById('connectBtn');
  const errorMsg = document.getElementById('connectErrorMsg');
  errorMsg.style.display = 'none';
  btn.textContent = 'Connecting…';
  btn.disabled    = true;

  const res = await send({ type: 'START_OAUTH' });

  // For Jam-ya mode the popup closes naturally when Chrome opens the new tab.
  // For Custom App (PKCE) the popup stays open; res carries success/failure.
  btn.textContent = 'Connect';
  btn.disabled    = false;

  if (res && res.ok === false) {
    const msg = res.error || 'Connection failed';
    errorMsg.textContent = msg.toLowerCase().includes('cancel') ? 'Auth cancelled — try again' : `Failed: ${msg}`;
    errorMsg.style.display = 'block';
  }
});
document.getElementById('logoutBtn').addEventListener('click', async () => {
  await send({ type: 'LOGOUT' });
});

// ── Credentials panel ─────────────────────────────────────────────────────────

const gearBtn      = document.getElementById('gearBtn');
const credsCard    = document.getElementById('credsCard');
const credsSaveBtn  = document.getElementById('credsSaveBtn');
const credsSavedMsg = document.getElementById('credsSavedMsg');

// Mode toggle (Jam-ya vs Custom App)
const modeJamya   = document.getElementById('modeJamya');
const modeCustom  = document.getElementById('modeCustom');
const jamyaPanel  = document.getElementById('jamyaPanel');
const customPanel = document.getElementById('customPanel');

async function setMode(mode) {
  const isCustom = mode === 'custom';
  modeJamya.classList.toggle('active', !isCustom);
  modeCustom.classList.toggle('active', isCustom);
  jamyaPanel.style.display  = isCustom ? 'none'  : 'block';
  customPanel.style.display = isCustom ? 'block' : 'none';
  document.getElementById('credsSaveBtn').style.display = isCustom ? 'inline-block' : 'none';
  document.getElementById('connectErrorMsg').style.display = 'none';
  await chrome.storage.local.set({ connectionMode: mode });
  // Switching to Jam-ya clears stored custom credentials from background
  if (!isCustom) {
    await chrome.storage.local.remove(['spotifyClientId', 'spotifyClientSecret']);
    await send({ type: 'SET_CREDENTIALS', clientId: null, clientSecret: null });
  }
}

modeJamya.addEventListener('click',  () => setMode('jamya'));
modeCustom.addEventListener('click', () => setMode('custom'));

gearBtn.addEventListener('click', async () => {
  const open = credsCard.style.display !== 'none';
  credsCard.style.display = open ? 'none' : 'block';
  gearBtn.classList.toggle('active', !open);
  if (!open) {
    // Re-read storage every time the panel opens to catch any stale state
    await loadCredentials();
    await populateRedirectUri();
  }
});

// Populate redirect URI (read-only — derived from extension ID)
async function populateRedirectUri() {
  try {
    const redirectUri = chrome.identity.getRedirectURL();
    document.getElementById('credsRedirectUri').value = redirectUri;
  } catch (_) {
    document.getElementById('credsRedirectUri').value = 'chrome.identity not available';
  }
}

// Load saved credentials and mode into inputs
async function loadCredentials() {
  const stored = await chrome.storage.local.get(['spotifyClientId', 'spotifyClientSecret', 'connectionMode']);
  const isCustom = stored.connectionMode === 'custom';
  modeJamya.classList.toggle('active', !isCustom);
  modeCustom.classList.toggle('active', isCustom);
  jamyaPanel.style.display  = isCustom ? 'none'  : 'block';
  customPanel.style.display = isCustom ? 'block' : 'none';
  document.getElementById('credsSaveBtn').style.display = isCustom ? 'inline-block' : 'none';
  if (stored.spotifyClientId)     document.getElementById('credsClientId').value     = stored.spotifyClientId;
  if (stored.spotifyClientSecret) document.getElementById('credsClientSecret').value = stored.spotifyClientSecret;
}

credsSaveBtn.addEventListener('click', async () => {
  const clientId     = document.getElementById('credsClientId').value.trim();
  const clientSecret = document.getElementById('credsClientSecret').value.trim();
  if (!clientId) {
    document.getElementById('credsClientId').focus();
    return;
  }
  await chrome.storage.local.set({ spotifyClientId: clientId, spotifyClientSecret: clientSecret });
  await send({ type: 'SET_CREDENTIALS', clientId, clientSecret });
  credsSavedMsg.style.display = 'block';
  setTimeout(() => { credsSavedMsg.style.display = 'none'; }, 3000);
});

// ── Init ──────────────────────────────────────────────────────────────────────

(async () => {
  const s = await send({ type: 'GET_STATE' });
  if (s) applyState(s);
  await populateRedirectUri();
  await loadCredentials();
})();
