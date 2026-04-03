/**
 * content-jamya.js — Runs in ISOLATED world on jam-ya.com (document_idle)
 *
 * Reads the Spotify token that the Jemya React app stores in localStorage
 * and forwards it to the background service worker. This means:
 *
 * - If the user is already signed into jam-ya.com the extension gets a token
 *   automatically, with no OAuth dialog.
 * - When the user is redirected to jam-ya.com/callback?code=... after a
 *   manual "Connect" from the popup, we wait 2 s for the React app to finish
 *   exchanging the code before reading the resulting token.
 *
 * The React app stores the token as JSON under the key "jemya_token":
 *   { access_token, refresh_token, expires_at, ... }
 */

function tryReadToken() {
  try {
    const raw = localStorage.getItem('jemya_token');
    if (!raw) return;

    const tokenInfo = JSON.parse(raw);
    if (!tokenInfo?.access_token) return;

    chrome.runtime.sendMessage({
      type: 'JAMYA_TOKEN',
      token: tokenInfo.access_token,
      tokenInfo,
    }).catch(() => {});
  } catch (_) {
    // Malformed localStorage entry — ignore
  }
}

// On the OAuth callback page, React needs a moment to exchange the code and
// write to localStorage before we read it.
if (window.location.pathname.startsWith('/callback')) {
  setTimeout(tryReadToken, 2000);
} else {
  tryReadToken();
}
