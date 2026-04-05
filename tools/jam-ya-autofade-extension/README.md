# Jam-Ya Auto Fade Chrome Extension

A Chrome extension that adds smooth, automatic crossfading to Spotify Web Player tracks using the official Spotify Web API. Part of the **Jam-Ya suite** for enhanced music experience.

## Features

✨ **Smooth Auto Fade** - Automatically fade out the current track while fading in the next track  
🎚️ **Separate Fade Controls** - Independent fade-out and fade-in durations (0-15 seconds)  
📈 **Multiple Fade Curves** - Choose from Linear, S-Curve, Exponential, and Sine curves  
🎛️ **Minimum Volume Control** - Set the lowest volume point during transitions (0-50%)  
🎵 **Full Player Controls** - Play/pause, skip, seek, and volume control built-in  
📜 **Queue Display** - View and jump to upcoming tracks (available in enlarged window)  
🪟 **Detachable Window** - Pin the player in a separate, draggable window  
🔐 **Flexible Authentication** - Connect with your own Spotify app or use Jam-Ya's quick connect  
💾 **Persistent Settings** - All settings saved across browser restarts  
🚀 **Spotify Web API** - Pure API integration, no DOM manipulation  

## Installation

### 1. Prerequisites

You'll need one of the following:
- **Option A**: Your own Spotify Developer App (recommended for full control)
- **Option B**: Use Jam-Ya's authentication (quick setup)

#### Option A: Create Your Own Spotify App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **"Create app"**
3. Fill in:
   - **App name**: Any name (e.g., "My Chrome Crossfade")
   - **App description**: Any description
   - **Redirect URI**: Get this from the extension after loading (see below)
   - **APIs**: Select "Web API"
4. Save your **Client ID**

### 2. Load the Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **"Developer mode"** (toggle in the top-right corner)
3. Click **"Load unpacked"**
4. Select the `tools/spotify-crossfade-extension` folder
5. The extension should now appear in your extensions list

### 3. Connect to Spotify

#### Using Your Own App (Option A):
1. Click the extension icon in Chrome toolbar
2. Go to **Connection** tab
3. The **Redirect URI** is already filled in - **copy it**
4. Go back to your Spotify app settings and add this Redirect URI
5. Paste your **Client ID** from Spotify Developer Dashboard
6. Click **"Save & Connect"**
7. Authorize in the Spotify login window

#### Using Jam-Ya App (Option B):
1. Click the extension icon
2. Go to **Connection** tab
3. Click **"Use Jam-Ya App →"** link
4. Click **"Connect"**
5. Authorize in the Spotify login window

### 4. Start Using

1. Navigate to [Spotify Web Player](https://open.spotify.com)
2. Start playing music
3. The extension automatically displays current track and controls
4. Toggle **"Enable auto fade"** in the **Auto Fade** tab
5. Adjust fade settings to your preference

## How It Works

The extension uses the official Spotify Web API:
1. **OAuth 2.0 PKCE** authentication for secure access
2. **Polling** Spotify's playback state every 500ms
3. **Smart fade detection** - triggers when track is ending
4. **Volume API** - smoothly adjusts volume using `/v1/me/player/volume`
5. **Queue management** - fetches and displays upcoming tracks
6. **Playback control** - play, pause, skip, seek via API

**Important**: Only works with **Spotify Web Player** - the extension cannot control the desktop app.

## Configuration

### Auto Fade Settings

- **Enable auto fade**: Master toggle
- **Fade out duration**: 0-15 seconds (default: 2.5s)
- **Fade in duration**: 0-15 seconds (default: 4.5s)
- **Minimum volume**: 0-50% (default: 15%)
- **Fade curves**: Choose curve type for each fade direction
  - **Linear**: Constant rate
  - **S-Curve**: Smooth acceleration and deceleration
  - **Exponential In/Out**: Gradual or sharp transitions
  - **Sine In/Out**: Natural sinusoidal curves

### Advanced Features

- **Detach Window**: Open player in a separate, always-on-top window
- **Queue Display**: Visible when window height > 650px, click tracks +1/+2 to skip
- **Progress Bar**: Click to seek to any position
- **Volume Control**: Direct Spotify volume slider

## Troubleshooting

### Auto fade not working
- Ensure you're using **Spotify Web Player** (`open.spotify.com`), not the desktop app
- Check that **auto fade is enabled** in the extension
- Verify the extension has a **green checkmark** (✓) showing connected status
- Refresh the Spotify Web Player tab and reconnect if needed

### "Not on Web Player" warning
- The extension only controls Spotify Web Player
- Make sure playback is active in the browser, not the desktop app
- Transfer playback to "Web Player" in Spotify's device list

### Rate limiting issues
- Spotify limits excessive volume API calls
- If you see rate warnings, reduce fade duration or avoid manual volume changes during fades
- Queue skipping limited to +1/+2 positions to avoid rate limits

### Connection issues
- Click **"Logout"** and reconnect
- Verify your Spotify app's **Redirect URI** matches exactly
- Check Chrome console (F12) for `[bg]` logs
- Make sure your Spotify app is not in "Development Mode" with user limits

### Performance
- Extension polls every 500ms - minimal CPU impact
- All fade calculations run in background service worker
- Queue limited to 20 tracks for performance

## Permissions

The extension requests:
- **storage**: Save settings and authentication tokens
- **alarms**: Periodic polling of Spotify playback state
- **identity**: Generate OAuth redirect URL
- **host_permissions**: Access Spotify API and Jam-Ya authentication endpoints

## Limitations

- ⚠️ **Web Player Only** - Cannot control Spotify desktop app
- ⚠️ **Active Playback Required** - Must have music playing in web player
- ⚠️ **Rate Limits** - Spotify API has undocumented limits on rapid volume changes
- ⚠️ **Queue Skipping** - Limited to next 2 tracks to avoid rate limiting
- ⚠️ **No Offline** - Requires internet connection for API access

## Development

### Build

```bash
cd tools
./build_chrome_extension.sh
```

Creates a ZIP file in `dist/` for Chrome Web Store submission.

### Files

- `manifest.json` - Extension configuration (v3)
- `background.js` - Service worker with OAuth, polling, fade engine
- `popup.html` / `popup.js` - UI with tabs, player, settings
- `content-bridge.js` - Minimal bridge for Web Player integration
- `content-jamya.js` - Jam-Ya authentication flow handler
- `icons/` - Extension icons (128px on/off states)

## Privacy

- Extension stores OAuth tokens locally using `chrome.storage.local`
- No data sent to external servers except Spotify API and authentication endpoints
- Jam-Ya authentication endpoint only used if you choose "Use Jam-Ya App"
- Client ID stored locally, never transmitted to Jam-Ya

## Support

For issues or suggestions:
- Open an issue in the Jemya GitHub repository
- Check extension console logs (F12 → Console) for error messages
- Try logout/reconnect if experiencing authentication issues

---

**Version**: 2.4.0  
**Part of**: Jam-Ya suite · [jam-ya.com](https://jam-ya.com)  
**Compatible**: Chrome/Edge on macOS, Windows, Linux  
**API**: Spotify Web API with OAuth 2.0 PKCE
