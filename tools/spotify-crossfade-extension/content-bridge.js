/**
 * content-bridge.js — Runs in ISOLATED world on open.spotify.com
 *
 * Keeps the background service worker alive via a persistent port while
 * the Spotify Web Player tab is open (MV3 service worker keepalive).
 */

/** Returns false once the extension has been reloaded/updated and this
 *  content script's context is no longer valid. All chrome.runtime calls
 *  throw "Extension context invalidated" in that state. */
function isContextValid() {
  return !!chrome.runtime?.id;
}

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
