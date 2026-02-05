# How to Use MCP Mode in Jemya

## What is MCP Mode?

MCP (Model Context Protocol) Mode enables cross-playlist operations. Instead of being restricted to modifying a single playlist, the AI can now:
- **Read multiple playlists** simultaneously
- **Combine playlists** into one
- **Merge and deduplicate** tracks across playlists
- **Split playlists** by criteria (genre, mood, tempo)
- **Analyze** your entire playlist collection

## Enabling MCP Mode

1. **Login to Spotify** (if not already logged in)
2. Click **"⚙️ Advanced Settings"** in the sidebar
3. Check **"🔬 Enable MCP Mode (Experimental)"**
4. You'll see a blue info box confirming MCP Mode is active

## Example Commands

### Combine Playlists
```
"Combine my workout playlists into one"
"Merge Part 1, Part 2, and Part 3 playlists"
```

**What happens:**
1. AI calls `list_playlists()` to see your playlists
2. AI identifies matching playlists
3. AI calls `read_playlist()` for each one
4. AI plans the combination
5. AI explains what it found and how to combine them

### Merge with Deduplication
```
"Merge my jazz playlists but remove duplicate tracks"
```

**What happens:**
1. AI reads all jazz playlists
2. AI identifies duplicate tracks (same Spotify URI)
3. AI creates a unique list
4. AI explains the deduplication results

### Split Playlists
```
"Split my Mega Mix into upbeat and chill playlists"
```

**What happens:**
1. AI reads the Mega Mix playlist
2. AI analyzes track characteristics (tempo, energy, mood)
3. AI groups tracks into categories
4. AI explains the split plan

### Analyze Collection
```
"What are my top 5 longest playlists?"
"Show me all playlists created by me"
"Find playlists that have tracks by Coldplay"
```

## Understanding the Response

When MCP Mode is active, you'll see:

### 🔬 MCP Mode Active
The AI will show:
- **"Initializing..."** - Setting up MCP connection
- **"Calling AI..."** - Making function calls

### 🔧 Tools Used
At the bottom of the AI response, you'll see:
```
---
🔧 Tools Used: 3

1. `list_playlists()`
2. `read_playlist()`
3. `read_playlist()`
```

This shows which MCP tools the AI used to answer your question.

## MCP Mode vs Legacy Mode

### Legacy Mode (Default)
- ✅ Works with single playlist only
- ✅ Direct playlist enrichment
- ✅ Preview-before-apply workflow
- ✅ Streaming responses
- ❌ Cannot access multiple playlists

### MCP Mode (Experimental)
- ✅ Cross-playlist operations
- ✅ AI autonomous function calling
- ✅ Read from multiple playlists
- ✅ Create new playlists
- ⚠️ Non-streaming responses (full response at end)
- ⚠️ Write operations need testing

## Important Notes

1. **Read-Only Currently Safe**: MCP Mode has been tested with read operations (list_playlists, read_playlist, search_tracks)

2. **Write Operations Experimental**: Creating, adding, removing, and replacing tracks work in tests but should be used carefully in production

3. **No Preview Yet**: MCP Mode doesn't yet integrate with the Preview button. The AI will explain what it *would* do, but won't automatically execute writes

4. **Performance**: MCP Mode responses may be slightly slower due to function calling overhead

5. **Fallback**: If MCP Mode encounters an error, you'll see an error message suggesting to disable MCP Mode and try again

## Troubleshooting

### "MCP Mode error: ..."
- Disable MCP Mode in Advanced Settings
- Try your request again in Legacy Mode
- Check terminal output for detailed error logs

### AI doesn't recognize my playlist names
- Try using more specific names
- Use quotes: "combine 'Workout Mix' and 'Gym Jams'"
- Ask AI to list your playlists first

### Response is slow
- MCP Mode needs to make multiple API calls
- Each function call adds latency
- Complex operations (reading 5+ playlists) may take longer

## Future Enhancements

Coming soon to MCP Mode:
- [ ] Preview-before-apply for write operations
- [ ] Multi-playlist selector UI
- [ ] Visual progress indicators
- [ ] Streaming responses with function calls
- [ ] Undo/rollback capability
- [ ] Batch operations optimization

---

**Status**: ✅ Phase 3 Complete - MCP Mode available in Streamlit UI  
**Version**: v0.1.0-mcp  
**Last Updated**: February 5, 2026
