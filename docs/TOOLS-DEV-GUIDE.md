# Jemya Tools Development Guide

This guide explains how to create and integrate tools with Jemya.

## What are Jemya Tools?

Jemya Tools are extensions, integrations, or utilities that enhance the core Jemya experience. They can be:

- **Browser Extensions** - Chrome/Firefox extensions that add functionality to music streaming
- **Integrations** - Connections to external services or APIs
- **Standalone Utilities** - Command-line tools or scripts for playlist management
- **Plugins** - Add-ons that extend Jemya's AI capabilities

## Tool Structure

Each tool should have:

```
jemya/tools/
├── your-tool-name/
│   ├── manifest.json           # Tool metadata
│   ├── README.md               # Installation and usage instructions
│   ├── src/                    # Source code
│   └── dist/                   # Built/packaged files (if applicable)
```

## Creating a Chrome Extension Tool

### 1. Manifest File

Every tool should include a `manifest.json` describing it:

```json
{
  "id": "unique-tool-id",
  "name": "Your Tool Name",
  "version": "1.0.0",
  "description": "What your tool does",
  "type": "chrome-extension",
  "installationCost": "free",
  "author": "Your Name",
  "homepage": "https://github.com/jjHimmelreich/Jemya",
  "documentation": "README.md"
}
```

### 2. Implementation

- Use Jemya's color scheme: `#3B7EA5` (primary blue), `#121212` (dark background)
- Follow existing patterns in the extension (logging, storage, messaging)
- Test thoroughly on Spotify Web Player
- Document limitations clearly

### 3. Branding

All tools should:
- Display "Part of the Jemya Toolkit" or similar attribution
- Use Jemya's design system (fonts, colors, messaging)
- Link back to the main Jemya project
- Include the Jemya logo in UI where appropriate

## Adding Your Tool to the Tools Page

Once your tool is ready:

1. **Create subdirectory** in `tools/` with your tool name
2. **Add files** to the directory
3. **Update** `frontend/src/pages/ToolsPage.tsx` to include your tool in the `TOOLS` array:

```tsx
{
  id: 'your-tool-id',
  name: 'Your Tool Name',
  description: 'Brief description of what it does',
  icon: '🎯', // Choose an emoji
  status: 'available', // or 'coming-soon', 'installed'
  url: 'https://github.com/jjHimmelreich/Jemya/tree/<branch>/tools/your-tool-name',
  installation: 'chrome-extension', // or other type
}
```

4. **Submit PR** to the Jemya repository

## Tool Development Best Practices

### Security

- Never store sensitive user data (tokens, passwords) without encryption
- Use Chrome's `chrome.storage` API instead of localStorage
- Request minimum necessary permissions
- Validate all inputs from Spotify's DOM

### Performance

- Minimize injected code
- Use event delegation instead of watching every element
- Clean up event listeners when tool is disabled
- Profile memory usage on large playlists

### User Experience

- Provide clear settings UI with explanations
- Display status (enabled/disabled, active/inactive)
- Include help text in popups
- Handle errors gracefully with user-friendly messages

### Testing

- Test on various playlist sizes (small, medium, large)
- Test on different browsers/OSes before release
- Create a test playlist for reproducible testing
- Check console for errors (F12 in Spotify Web Player)

## Example Tool: Spotify Crossfade

The Spotify Crossfade extension shows a complete implementation:

```
tools/spotify-crossfade-extension/
├── manifest.json        # Chrome extension config
├── background.js        # Service worker
├── content-script.js    # Page injection
├── popup.html          # Settings UI
├── popup.js            # Settings logic
└── README.md           # Installation guide
```

**Key points from this tool:**

- Uses messaging between content script and injected script
- Handles Spotify's dynamic DOM
- Provides toggle and duration controls
- Includes comprehensive logging for debugging

## Distribution

### For Browser Extensions

- Host in the browser's extension store (Chrome Web Store, Firefox Add-ons)
- Or provide installation instructions for direct loading via `chrome://extensions/`

### For Other Tools

- Host on GitHub in the `tools/` directory
- Provide clear installation instructions
- Link from the Tools page

## Support & Feedback

- Include contact info in tool README
- Link to GitHub issues for bug reports
- Document known limitations
- Include troubleshooting section

## Contribution Workflow

1. Fork the Jemya repository
2. Create a new branch: `feature/add-tool-<tool-id>`
3. Add your tool to the `tools/` directory
4. Update `ToolsPage.tsx` with your tool's info
5. Create comprehensive README with installation steps
6. Submit PR with detailed description
7. Participate in code review

## Checklist Before Submission

- [ ] Tool is fully functional
- [ ] README includes installation and usage instructions
- [ ] Error handling is implemented
- [ ] Code is documented with comments
- [ ] Jemya branding is applied consistently
- [ ] Tool is tested in multiple scenarios
- [ ] No console errors or warnings
- [ ] Performance is acceptable
- [ ] Security considerations are addressed
- [ ] ToolsPage.tsx is updated with tool info

---

**Questions?** Create an issue in the Jemya repository or check existing tools for reference.
