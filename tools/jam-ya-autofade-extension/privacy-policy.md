# Privacy Policy

Extension: **Jam-Ya Auto Fade**  
Last updated: **April 5, 2026**

## 1. Overview

Jam-Ya Auto Fade (the Extension) is a Chrome browser extension that provides smooth crossfade volume control for the Spotify Web Player. This Privacy Policy explains what data the Extension accesses, how it is used, and what is never collected.

## 2. Data the Extension Accesses

### 2.1 Spotify OAuth Token Data

To control Spotify playback on your behalf, the Extension requires a Spotify OAuth access token.

- **Jam-ya mode:** The Extension reads the Spotify token payload from the `jemya_token` key in your browser `localStorage` on `jam-ya.com`. The payload is forwarded to the Extension background service worker and stored locally in `chrome.storage.local` on your device only. If a refresh token is present, refresh calls are made directly to `https://jam-ya.com/auth/refresh`.
- **Your Spotify App mode:** You provide your own Spotify Client ID. It is stored locally in `chrome.storage.local` on your device only. OAuth uses PKCE (no client secret) via `chrome.identity.launchWebAuthFlow`, and resulting tokens are stored locally on your device only.

### 2.2 Spotify Playback Data

The Extension polls the Spotify Web API (`api.spotify.com`) every few seconds to read current playback state (track name, artist, progress, volume, play/pause status). This data is used only for popup now-playing display and crossfade timing. It is not stored beyond your active session or sent to third parties.

## 3. Data We Do Not Collect

- We do not collect personal information.
- We do not track browsing history or activity on websites.
- We do not send data to external analytics services.
- We do not store Extension data on a remote server operated by this Extension.
- We do not sell, share, or monetize data.
- We do not read web page content beyond the specific `jemya_token` key on `jam-ya.com`. We do not scrape page content.

## 4. Local Storage

The following is stored locally on your device using `chrome.storage.local`:

- Spotify access token and expiry time
- Spotify Client ID (Your Spotify App mode only, if provided by you)
- Extension settings: crossfade duration, fade curves, minimum volume, enabled state
- Connection mode preference (Jam-Ya App or Your Spotify App)

This data remains until you log out within the Extension or uninstall it.

## 5. Permissions Justification

- `storage` - Save settings and tokens locally on your device.
- `alarms` - Schedule periodic polling of playback state.
- `identity` - Perform OAuth via `chrome.identity.launchWebAuthFlow` in Your Spotify App mode.
- `https://api.spotify.com/*` - Call Spotify Web API for playback state and control.
- `https://accounts.spotify.com/*` - Exchange OAuth authorization code for access token (Your Spotify App mode).
- `https://jam-ya.com/*` - Read token from `localStorage` on `jam-ya.com` and refresh it when needed.
- Content script on `jam-ya.com` - Read only the `jemya_token` localStorage key for token relay. We do not read or scrape page content on `open.spotify.com`.

## 6. Third-Party Services

The Extension communicates only with:

- [Spotify](https://www.spotify.com/legal/privacy-policy/) - playback control and OAuth
- [Jam-ya](https://jam-ya.com) - token relay and refresh (Jam-ya mode only)

No other third-party services, CDNs, or analytics providers are used.

## 7. Children's Privacy

This Extension is not age-restricted. We do not knowingly collect personal data from children.

## 8. Changes to This Policy

We may update this Privacy Policy from time to time. The Last updated date will reflect changes. The latest public copy is available at:

- https://jam-ya.com/chrome-extension/jam-ya-auto-fade/privacy-policy.html

Continued use of the Extension after an update constitutes acceptance of the revised policy.

## 9. Contact

If you have questions about this policy, open an issue in the Jemya repository:

- https://github.com/jjHimmelreich/Jemya
