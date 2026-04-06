/**
 * content-bridge.js — Runs in ISOLATED world on open.spotify.com
 *
 * Keeps the background service worker alive via a persistent port while
 * the Spotify Web Player tab is open (MV3 service worker keepalive).
 *
 * Also injects audio-processor.js into the page world for Web Audio EQ processing.
 */

/** Returns false once the extension has been reloaded/updated and this
 *  content script's context is no longer valid. All chrome.runtime calls
 *  throw "Extension context invalidated" in that state. */
function isContextValid() {
  return !!chrome.runtime?.id;
}

// ── Page-world audio processor injection ──────────────────────────────────────

function injectAudioProcessor() {
  if (window.JEMYA_EQ_INJECTED) return; // Already injected
  
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('audio-processor.js');
  script.onload = () => {
    console.log('[Jemya/bridge] 🎵 Audio processor script injected');
    script.remove();
  };
  script.onerror = () => {
    console.warn('[Jemya/bridge] ⚠️ Failed to inject audio processor');
    script.remove();
  };
  
  (document.head || document.documentElement).appendChild(script);
  window.JEMYA_EQ_INJECTED = true;
}

function postEqToPage(msg) {
  window.postMessage(msg, '*');
}

async function hydrateEqState() {
  try {
    const state = await chrome.runtime.sendMessage({ type: 'GET_STATE' });
    if (!state) return;

    postEqToPage({ type: 'JEMYA_EQ_INIT' });
    postEqToPage({ type: 'JEMYA_EQ_ENABLE', enabled: !!state.eqEnabled });

    const bands = state.eqState?.bands || {};
    const keys = ['hz32', 'hz64', 'hz125', 'hz250', 'hz500', 'hz1000', 'hz2000', 'hz4000', 'hz8000', 'hz16000'];
    keys.forEach((band) => {
      postEqToPage({ type: 'JEMYA_EQ_SET_BAND', band, gainDb: Number(bands[band] ?? 0) });
    });
  } catch (e) {
    console.warn('[Jemya/bridge] EQ hydrate failed:', e?.message);
  }
}

// Inject as soon as possible
if (document.head || document.documentElement) {
  injectAudioProcessor();
  setTimeout(hydrateEqState, 250);
} else {
  document.addEventListener('DOMContentLoaded', () => {
    injectAudioProcessor();
    setTimeout(hydrateEqState, 250);
  });
  // Fallback: inject after a short delay
  setTimeout(() => {
    injectAudioProcessor();
    setTimeout(hydrateEqState, 250);
  }, 100);
}

// ── Message relay: background → page world ───────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, _sendResponse) => {
  // Forward EQ messages to the page world via postMessage
  if (msg.type && msg.type.startsWith('EQ_')) {
    postEqToPage({
      type: 'JEMYA_EQ_' + msg.type,
      ...msg,
    });
  }
});

// ── Keepalive port ────────────────────────────────────────────────────────────
// Keeps the background service worker from sleeping while music is playing.
function connectKeepalive() {
  if (!isContextValid()) return; // extension reloaded — stop reconnecting
  try {
    const port = chrome.runtime.connect({ name: 'keepalive' });
    console.log('[Jemya/bridge] 🔗 Keepalive port connected');
    port.onDisconnect.addListener(() => {
      console.log('[Jemya/bridge] 🔁 Keepalive port disconnected — reconnecting…');
      setTimeout(connectKeepalive, 1000);
    });
  } catch (e) {
    console.warn('[Jemya/bridge] ⚠ Keepalive connect failed (context invalidated?):', e?.message);
  }
}

connectKeepalive();
