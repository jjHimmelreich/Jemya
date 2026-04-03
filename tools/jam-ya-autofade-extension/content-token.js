/**
 * content-token.js — Runs in MAIN world (page context) on open.spotify.com
 *
 * Wraps window.fetch AND XMLHttpRequest to intercept outgoing Spotify API
 * calls and capture the Bearer token. Posts via window.postMessage to the
 * ISOLATED world bridge script. No chrome.* APIs available here.
 */
(function () {
  'use strict';

  let _lastEmitted = null;

  function emitToken(token, source) {
    if (token === _lastEmitted) return; // already sent this token, skip
    _lastEmitted = token;
    console.log('[Jemya/token] 🔑 Bearer captured via', source, '→', token.slice(0, 12) + '…');
    window.postMessage({ _jemya: true, type: 'TOKEN', token }, '*');
  }

  // ── Fetch interception ──────────────────────────────────────────────────────
  const _fetch = window.fetch;

  window.fetch = function (...args) {
    try {
      // Resolve URL from string, URL object, or Request object
      const url =
        typeof args[0] === 'string' ? args[0]
        : args[0] instanceof URL    ? args[0].href
        : args[0] instanceof Request ? args[0].url
        : '';

      if (url.includes('.spotify.com')) {
        let auth = null;

        // Try init options headers first — avoid new Headers() as it throws
        // for non-standard header formats used by Spotify's connect protocol.
        const init = args[1];
        if (init?.headers) {
          if (init.headers instanceof Headers) {
            auth = init.headers.get('Authorization');
          } else if (typeof init.headers === 'object') {
            auth = init.headers['Authorization'] ?? init.headers['authorization'] ?? null;
          }
        }

        // Fall back to Request object headers
        if (!auth && args[0] instanceof Request) {
          try { auth = args[0].headers.get('Authorization'); } catch (_) {}
        }

        if (auth?.startsWith('Bearer ')) {
          const tok = auth.slice(7);
          emitToken(tok, 'fetch');
        } else if (
          url.includes('api.spotify.com') ||
          url.includes('accounts.spotify.com') ||
          url.includes('spclient')
        ) {
          // Only warn for endpoints that are expected to carry auth
          console.log('[Jemya/token] ⚠ API call with no Bearer header:', url.split('?')[0]);
        }
      }
    } catch (_) {
      // Never break the page's own fetch calls
    }

    return _fetch.apply(this, args);
  };

  // XHR interception intentionally omitted — patching XHR.prototype crashes
  // the Spotify web player. Fetch interception is sufficient to capture tokens.

})();
