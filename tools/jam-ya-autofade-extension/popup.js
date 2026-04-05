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
  // Auth status in header and connection tab
  const authEl = document.getElementById('authStatus');
  const authTextEl = document.getElementById('authStatusText');
  const jamyaBtn = document.getElementById('jamyaConnectBtn');
  const customBtn = document.getElementById('customConnectBtn');
  
  if (s.hasToken) {
    authEl.textContent = '✓';
    authEl.className   = 'auth-status ok';
    authTextEl.textContent = 'Connected';
    jamyaBtn.textContent = 'Disconnect';
    jamyaBtn.className = 'logout-btn';
    customBtn.textContent = 'Disconnect';
    customBtn.className = 'logout-btn';
  } else {
    authEl.textContent = '✗';
    authEl.className   = 'auth-status err';
    authTextEl.textContent = 'Not connected';
    jamyaBtn.textContent = 'Connect';
    jamyaBtn.className = 'connect-btn';
    customBtn.textContent = 'Save & Connect';
    customBtn.className = 'connect-btn';
  }

  // Connected / disconnected UI state
  const isConnected = !!s.hasToken;
  const isWebPlayer = s.deviceName?.toLowerCase().includes('web player') ?? false;
  const canControl = isConnected && isWebPlayer;
  
  document.getElementById('setupHint').style.display     = isConnected ? 'none' : 'block';
  document.getElementById('trackName').style.display     = isConnected ? ''     : 'none';
  document.getElementById('artistName').style.display    = isConnected ? ''     : 'none';
  document.getElementById('progressBar').classList.toggle('locked',     !canControl);
  document.querySelector('.progress-times').classList.toggle('locked',   !canControl);
  document.querySelector('.controls').classList.toggle('locked',         !canControl);
  document.getElementById('volumeSlider').parentElement.classList.toggle('locked', !canControl);

  // Track
  const trackEl  = document.getElementById('trackName');
  const artistEl = document.getElementById('artistName');
  const deviceEl = document.getElementById('deviceInfo');
  if (s.trackName) {
    trackEl.textContent  = s.trackName;
    trackEl.className    = 'track-name';
    artistEl.textContent = s.artistName ?? '';
  } else {
    trackEl.textContent  = 'Nothing playing';
    trackEl.className    = 'track-name empty';
    artistEl.textContent = '';
  }

  // Device info
  if (s.deviceName && isConnected) {
    document.getElementById('deviceName').textContent = s.deviceName;
    deviceEl.classList.add('visible');
  } else {
    deviceEl.classList.remove('visible');
  }

  // Device warning when controls are locked
  document.getElementById('deviceWarning').style.display = 
    (isConnected && !isWebPlayer) ? 'block' : 'none';

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
    .classList.toggle('on', s.hasToken ? (s.crossfadeEnabled ?? false) : false);
  const fadeOut = s.fadeOutDuration ?? 2500;
  document.getElementById('fadeOutSlider').value = fadeOut;
  document.getElementById('fadeOutValue').textContent = `${(fadeOut / 1000).toFixed(1)}s`;
  const fadeIn = s.fadeInDuration ?? 4500;
  document.getElementById('fadeInSlider').value = fadeIn;
  document.getElementById('fadeInValue').textContent = `${(fadeIn / 1000).toFixed(1)}s`;
  const minVol = s.minVolume ?? 15;
  document.getElementById('minVolumeSlider').value = minVol;
  document.getElementById('minVolumeValue').textContent = `${minVol}%`;
  document.getElementById('fadeOutCurveSelect').value = s.fadeOutCurveName ?? 'scurve';
  document.getElementById('fadeInCurveSelect').value  = s.fadeInCurveName  ?? 'scurve';

  // EQ Settings
  const eqEnabled = s.eqEnabled ?? false;
  document.getElementById('enableEqToggle').classList.toggle('on', eqEnabled);
  document.getElementById('eqControls').style.display = eqEnabled ? 'block' : 'none';
  
  if (s.eqState) {
    console.log('[Popup] Rendering EQ state:', s.eqState);
    document.getElementById('eqPresetSelect').value = s.eqState.currentPreset ?? 'flat';
    
    const eqLow = s.eqState.bands?.low ?? 0;
    document.getElementById('eqLowSlider').value = eqLow;
    document.getElementById('eqLowValue').textContent = `${eqLow > 0 ? '+' : ''}${eqLow} dB`;
    
    const eqMid = s.eqState.bands?.mid ?? 0;
    document.getElementById('eqMidSlider').value = eqMid;
    document.getElementById('eqMidValue').textContent = `${eqMid > 0 ? '+' : ''}${eqMid} dB`;
    
    const eqHigh = s.eqState.bands?.high ?? 0;
    document.getElementById('eqHighSlider').value = eqHigh;
    document.getElementById('eqHighValue').textContent = `${eqHigh > 0 ? '+' : ''}${eqHigh} dB`;
  }

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
  
  // Fetch and render queue
  fetchQueue();
}

// ── Queue ─────────────────────────────────────────────────────────────────────

async function fetchQueue() {
  if (!lastState?.hasToken) {
    renderQueue([]);
    return;
  }
  
  try {
    const res = await send({ type: 'FETCH_QUEUE' });
    if (res && res.ok && res.queue) {
      renderQueue(res.queue, lastState.trackId);
    } else {
      renderQueue([]);
    }
  } catch (e) {
    renderQueue([]);
  }
}

function renderQueue(queue, currentTrackId) {
  const queueList = document.getElementById('queueList');
  
  if (!queue || queue.length === 0) {
    queueList.innerHTML = '<div class="queue-empty">No upcoming tracks</div>';
    return;
  }
  
  // Limit queue display to first 20 tracks to avoid showing endless repeats
  const displayQueue = queue.slice(0, 20);
  const hasMore = queue.length > 20;
  
  queueList.innerHTML = displayQueue.map((track, index) => {
    const isCurrent = track.id === currentTrackId;
    const artistNames = track.artists?.map(a => a.name).join(', ') || 'Unknown Artist';
    const isClickable = index <= 1; // Only +1 and +2 are clickable
    return `
      <div class="queue-item${isCurrent ? ' current' : ''}${!isClickable ? ' not-clickable' : ''}" data-index="${index}" data-position="+${index + 1}">
        <div class="queue-track-name">${escapeHtml(track.name)}</div>
        <div class="queue-artist-name">${escapeHtml(artistNames)}</div>
      </div>
    `;
  }).join('') + (hasMore ? '<div class="queue-empty" style="margin-top:8px;padding:8px">...and ' + (queue.length - 20) + ' more tracks</div>' : '');
  
  // Add click handlers only to clickable queue items
  queueList.querySelectorAll('.queue-item:not(.not-clickable):not(.current)').forEach(item => {
    item.addEventListener('click', () => {
      const index = parseInt(item.dataset.index, 10);
      if (!isNaN(index)) {
        playQueueTrack(index);
      }
    });
  });
}

async function playQueueTrack(queueIndex) {
  console.log('Requesting skip to queue index:', queueIndex);
  // Skip to the track by its position in the queue
  const res = await send({ type: 'PLAY_QUEUE_TRACK', queueIndex });
  console.log('Skip response:', res);
  if (!res || !res.ok) {
    const errorMsg = res?.error || 'Unknown error';
    console.error('Failed to play queue track:', errorMsg, 'Full response:', res);
    // Show user-friendly error (could add a toast notification here)
    alert(`Could not skip to track: ${errorMsg}`);
  } else {
    console.log('Successfully skipped to queue position', queueIndex);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
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
  if (!lastState?.hasToken) {
    const notice = document.getElementById('connectNotice');
    notice.style.display = 'block';
    setTimeout(() => { notice.style.display = 'none'; }, 3000);
    return;
  }
  send({ type: 'SET_SETTING', key: 'crossfadeEnabled', value: !(lastState?.crossfadeEnabled ?? false) });
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

// Jam-Ya connection button
document.getElementById('jamyaConnectBtn').addEventListener('click', async () => {
  const btn = document.getElementById('jamyaConnectBtn');
  const errorMsg = document.getElementById('connectErrorMsg');
  
  // If already connected, disconnect
  if (btn.textContent === 'Disconnect') {
    await send({ type: 'LOGOUT' });
    return;
  }
  
  // Otherwise connect with Jam-Ya app
  errorMsg.style.display = 'none';
  btn.textContent = 'Connecting…';
  btn.disabled = true;
  
  const res = await send({ type: 'START_OAUTH', mode: 'jamya', clientId: null });
  
  btn.textContent = 'Connect';
  btn.disabled = false;
  
  if (res && res.ok === false) {
    const msg = res.error || 'Connection failed';
    errorMsg.textContent = msg.toLowerCase().includes('cancel') ? 'Auth cancelled — try again' : `Failed: ${msg}`;
    errorMsg.style.display = 'block';
  }
});

// Custom app connection button
document.getElementById('customConnectBtn').addEventListener('click', async () => {
  const btn = document.getElementById('customConnectBtn');
  const errorMsg = document.getElementById('connectErrorMsg');
  
  // If already connected, disconnect
  if (btn.textContent === 'Disconnect') {
    await send({ type: 'LOGOUT' });
    return;
  }
  
  // Otherwise save credentials and connect
  const clientId = document.getElementById('credsClientId').value.trim();
  if (!clientId) {
    errorMsg.textContent = 'Please enter your Spotify Client ID first';
    errorMsg.style.display = 'block';
    document.getElementById('credsClientId').focus();
    return;
  }
  
  errorMsg.style.display = 'none';
  
  // Save credentials
  await chrome.storage.local.set({ spotifyClientId: clientId });
  await send({ type: 'SET_CREDENTIALS', clientId });
  
  // Connect
  btn.textContent = 'Connecting…';
  btn.disabled = true;
  
  const res = await send({ type: 'START_OAUTH', mode: 'pkce', clientId });
  
  btn.textContent = 'Save & Connect';
  btn.disabled = false;
  
  if (res && res.ok === false) {
    const msg = res.error || 'Connection failed';
    errorMsg.textContent = msg.toLowerCase().includes('cancel') ? 'Auth cancelled — try again' : `Failed: ${msg}`;
    errorMsg.style.display = 'block';
  }
});

// ── Tab switching ─────────────────────────────────────────────────────────────

const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    const targetTab = btn.dataset.tab;
    
    // Update button states
    tabButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    // Update content visibility
    tabContents.forEach(content => {
      if (content.id === `tab-${targetTab}`) {
        content.classList.add('active');
      } else {
        content.classList.remove('active');
      }
    });
  });
});

// ── Connection settings ───────────────────────────────────────────────────────

const showCustomLink = document.getElementById('showCustomLink');
const showJamyaLink  = document.getElementById('showJamyaLink');
const jamyaPanel  = document.getElementById('jamyaPanel');
const customPanel = document.getElementById('customPanel');

async function setMode(mode) {
  const isCustom = mode === 'custom';
  jamyaPanel.style.display  = isCustom ? 'none'  : 'block';
  customPanel.style.display = isCustom ? 'block' : 'none';
  document.getElementById('connectErrorMsg').style.display = 'none';
  await chrome.storage.local.set({ connectionMode: mode });
}

showCustomLink.addEventListener('click',  () => setMode('custom'));
showJamyaLink.addEventListener('click', () => setMode('jamya'));

// Populate redirect URI on load
async function populateRedirectUri() {
  try {
    const redirectUri = chrome.identity.getRedirectURL();
    document.getElementById('credsRedirectUri').value = redirectUri;
  } catch (_) {
    document.getElementById('credsRedirectUri').value = 'chrome.identity not available';
  }
}

// Load saved credentials and mode
async function loadCredentials() {
  const stored = await chrome.storage.local.get(['spotifyClientId', 'connectionMode']);
  // Default to custom mode if not set
  const isCustom = stored.connectionMode !== 'jamya';
  jamyaPanel.style.display  = isCustom ? 'none'  : 'block';
  customPanel.style.display = isCustom ? 'block' : 'none';
  if (stored.spotifyClientId) document.getElementById('credsClientId').value = stored.spotifyClientId;
}

// ── EQ Controls ──────────────────────────────────────────────────────────────

// EQ Enable toggle
document.getElementById('enableEqToggle').addEventListener('click', async () => {
  const toggle = document.getElementById('enableEqToggle');
  const eqControls = document.getElementById('eqControls');
  const isEnabled = toggle.classList.contains('on');
  const newState = !isEnabled;
  
  toggle.classList.toggle('on', newState);
  eqControls.style.display = newState ? 'block' : 'none';
  
  await send({ type: 'EQ_ENABLE', enabled: newState });
});

// EQ Preset dropdown
document.getElementById('eqPresetSelect').addEventListener('change', async (e) => {
  const preset = e.target.value;
  await send({ type: 'EQ_SET_PRESET', preset });
});

// EQ Band sliders
['Low', 'Mid', 'High'].forEach(band => {
  const bandLower = band.toLowerCase();
  const slider = document.getElementById(`eq${band}Slider`);
  const valueEl = document.getElementById(`eq${band}Value`);
  
  slider.addEventListener('input', async (e) => {
    const value = parseInt(e.target.value);
    valueEl.textContent = `${value > 0 ? '+' : ''}${value} dB`;
    await send({ type: 'EQ_SET_BAND', band: bandLower, value });
  });
});

// ── Detach window ─────────────────────────────────────────────────────────────

const detachBtn = document.getElementById('detachBtn');

// Hide detach button if we're already in a detached window
// (detect by checking if we're in a popup-type window)
chrome.windows.getCurrent((win) => {
  if (win.type === 'popup') {
    detachBtn.style.display = 'none';
    // Apply fixed height layout for detached window
    document.body.classList.add('detached-window');
  }
});

detachBtn.addEventListener('click', async () => {
  const res = await send({ type: 'DETACH_WINDOW' });
  if (res && res.ok) {
    // Close the current popup after successfully opening/focusing the detached window
    window.close();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

(async () => {
  await loadCredentials();
  await populateRedirectUri();
  const s = await send({ type: 'GET_STATE' });
  if (s) applyState(s);
})();
