# Jemya Spotify Crossfade Chrome Extension

A Chrome extension that adds crossfade functionality to Spotify's web player, mimicking the desktop app's crossfade feature. Part of the **Jemya Toolkit** for enhanced music experience.

## Features

✨ **Smooth Crossfade** - Gradually fade out the current track while fading in the next track  
⚙️ **Configurable Duration** - Set crossfade duration from 1 to 10 seconds (default: 5 seconds)  
🎚️ **Easy Toggle** - Enable/disable crossfade with a single click  
🚀 **Lightweight** - Minimal performance impact on the web player  
🎯 **Jemya Branded** - Integrates seamlessly with the Jemya ecosystem  

## Installation

### 1. Prepare the Extension

The extension files are located in the `tools/spotify-crossfade-extension` directory:
- `manifest.json` - Extension configuration
- `content-script.js` - Core crossfade logic
- `popup.html` / `popup.js` - Settings UI with Jemya branding
- `background.js` - Service worker

### 2. Load in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **"Developer mode"** (toggle in the top-right corner)
3. Click **"Load unpacked"**
4. Select this folder (`spotify-crossfade-extension`)
5. The extension should now appear in your extensions list

### 3. Use the Extension

1. Navigate to [Spotify Web Player](https://open.spotify.com)
2. Click the **extension icon** in your Chrome toolbar
3. **Toggle** crossfade on/off
4. **Adjust** the crossfade duration (1-10 seconds)
5. **Enjoy** smooth track transitions!

## How It Works

The extension:
1. Injects into the Spotify web player's page context
2. Monitors for track changes using Spotify's DOM
3. When a new track starts playing:
   - Gradually reduces the volume of the fading-out audio
   - Simultaneously increases the volume of the new track
   - Creates a smooth transition over your specified duration

## Troubleshooting

### Crossfade not working
- Make sure the extension is enabled on `chrome://extensions/`
- Refresh the Spotify web player tab
- Check that you're playing music (not paused)
- Open browser console (F12) and look for `[Jemya Crossfade]` logs

### Audio level issues
- Adjust your Spotify volume separately from the crossfade duration
- Crossfade works by modulating the player's volume, so your base volume remains intact

### Performance concerns
- The extension has minimal overhead
- All operations are contained to the Spotify tab
- Works smoothly on modern machines

## Future Enhancements

- [ ] Advanced fade curves (linear, exponential, logarithmic)
- [ ] Separate fade-in and fade-out durations
- [ ] Sync with desktop app settings
- [ ] Visual crossfade indicator in player
- [ ] Per-playlist crossfade settings

## Limitations

- Crossfade only works on the Spotify web player (not the desktop app)
- Requires audio to be playing from the Spotify web player
- Volume changes during crossfade override manual volume adjustments briefly

## Support

For issues or suggestions, please check the Jemya repository or reload the extension with `chrome://extensions/`.

---

**Version**: 1.0.0  
**Part of**: Jemya - AI-Powered Music Playlist Manager  
**Compatible**: Chrome/Edge on macOS, Windows, Linux
