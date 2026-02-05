# MCP Hybrid Architecture Design

## Overview
Hybrid architecture combining Streamlit UI with MCP (Model Context Protocol) server to enable cross-playlist operations while maintaining user-friendly interface and preview-before-apply workflow.

## Current Limitations
- ❌ Cannot combine multiple playlists in one conversation
- ❌ Each playlist has isolated conversation context
- ❌ No cross-playlist operations (e.g., "merge Part 1, Part 2, Part 3")
- ❌ AI cannot read from multiple playlists simultaneously

## Goals
- ✅ Enable cross-playlist operations
- ✅ Keep Streamlit UI for user interactions
- ✅ Maintain preview-before-apply safety pattern
- ✅ Use same OpenAI model with function calling
- ✅ No additional AI services needed

---

## Architecture Components

### 1. MCP Server (`spotify_mcp_server.py`)
**Purpose:** Expose Spotify operations as MCP tools

**MCP Tools:**
```python
# Read Operations
- read_playlist(playlist_id: str) -> List[Track]
  Returns: [{"track_name", "artist", "uri", "position"}]
  
- list_playlists() -> List[Playlist]
  Returns: [{"id", "name", "track_count", "owner"}]
  
- search_tracks(query: str, limit: int) -> List[Track]
  Returns: Spotify search results

# Write Operations  
- create_playlist(name: str, description: str, public: bool) -> str
  Returns: playlist_id
  
- add_tracks(playlist_id: str, tracks: List[Track], position: str) -> Result
  Returns: {"added_count", "failed_tracks"}
  
- remove_tracks(playlist_id: str, tracks: List[Track]) -> Result
  Returns: {"removed_count"}
  
- replace_playlist(playlist_id: str, tracks: List[Track]) -> Result
  Returns: {"added_count", "removed_count"}
```

**Implementation:**
- Built on `mcp` Python package
- Uses stdio transport (local process)
- Wraps existing `SpotifyManager` methods
- Handles authentication via token passed from main app

---

### 2. Streamlit UI (existing `app.py`)
**Keeps:**
- Chat interface (`st.chat_message`, `st.chat_input`)
- Playlist selector
- User authentication flow
- Preview display
- Apply button with confirmation
- Conversation persistence

**Removes:**
- Direct Spotify API calls from conversation flow
- Playlist-specific conversation restriction

**Adds:**
- MCP client connection
- Multi-playlist context selector
- Enhanced preview showing cross-playlist operations

---

### 3. MCP Integration Layer (`mcp_manager.py`)
**Purpose:** Bridge between Streamlit UI and MCP server

```python
class MCPManager:
    def __init__(self, spotify_token: str):
        self.client = MCPClient(server_path="./spotify_mcp_server.py")
        self.token = spotify_token
        
    async def get_tools_for_openai(self) -> List[Dict]:
        """Convert MCP tools to OpenAI function definitions"""
        tools = await self.client.list_tools()
        return [self._convert_to_openai_format(tool) for tool in tools]
    
    async def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Execute MCP tool and return result"""
        return await self.client.call_tool(tool_name, arguments)
    
    async def execute_tool_calls(self, tool_calls: List) -> List[Dict]:
        """Execute multiple OpenAI function calls via MCP"""
        results = []
        for call in tool_calls:
            result = await self.execute_tool(call.function.name, 
                                            json.loads(call.function.arguments))
            results.append({
                "tool_call_id": call.id,
                "role": "tool",
                "name": call.function.name,
                "content": json.dumps(result)
            })
        return results
```

---

### 4. Enhanced AI Manager (`ai_manager.py`)
**Updates:**
- Add function calling support
- Pass MCP tools to OpenAI
- Handle tool execution responses

```python
class AIManager:
    def __init__(self, mcp_manager: MCPManager):
        self.mcp_manager = mcp_manager
        self.client = OpenAI(api_key=conf.OPENAI_KEY)
    
    async def generate_playlist_with_tools(self, 
                                          user_request: str,
                                          conversation_history: List[Dict]) -> Dict:
        """Generate playlist using MCP tools"""
        
        # Get MCP tools for OpenAI
        tools = await self.mcp_manager.get_tools_for_openai()
        
        # Initial AI call with tools
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history + [
                {"role": "user", "content": user_request}
            ],
            tools=tools,
            tool_choice="auto"
        )
        
        # Handle function calls
        if response.choices[0].message.tool_calls:
            # Execute tools via MCP
            tool_results = await self.mcp_manager.execute_tool_calls(
                response.choices[0].message.tool_calls
            )
            
            # Send results back to AI for final response
            final_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversation_history + [
                    {"role": "user", "content": user_request},
                    response.choices[0].message,
                    *tool_results
                ]
            )
            
            return {
                "response": final_response.choices[0].message.content,
                "tool_calls": response.choices[0].message.tool_calls,
                "tool_results": tool_results
            }
        
        return {
            "response": response.choices[0].message.content,
            "tool_calls": [],
            "tool_results": []
        }
```

---

## User Flows

### Flow 1: Combine Multiple Playlists
**User Request:** "Combine Part 1, Part 2, and Part 3 into a new playlist called Complete Mix"

**AI Execution:**
1. `list_playlists()` → finds Part 1, Part 2, Part 3 IDs
2. `read_playlist(part1_id)` → gets 50 tracks
3. `read_playlist(part2_id)` → gets 45 tracks
4. `read_playlist(part3_id)` → gets 30 tracks
5. `create_playlist("Complete Mix")` → returns new_playlist_id
6. `add_tracks(new_playlist_id, combined_125_tracks)` → adds all tracks

**UI Display:**
```
🎵 Preview: Complete Mix (New Playlist)

Will create new playlist with 125 tracks:
- 50 tracks from Part 1
- 45 tracks from Part 2
- 30 tracks from Part 3

[Show Details ▼] [Apply Changes] [Cancel]
```

**User clicks Apply** → MCP executes final `create_playlist` + `add_tracks`

---

### Flow 2: Smart Playlist Merging with Deduplication
**User Request:** "Merge my workout playlists but remove duplicates and sort by tempo"

**AI Execution:**
1. `list_playlists()` → finds "Workout Mix", "Gym Jams", "Cardio Beats"
2. `read_playlist(workout_id)` → gets tracks
3. `read_playlist(gym_id)` → gets tracks
4. `read_playlist(cardio_id)` → gets tracks
5. AI deduplicates (same track URI)
6. AI sorts by tempo (uses audio features from Spotify)
7. `create_playlist("Ultimate Workout")` → new_id
8. `add_tracks(new_id, deduplicated_sorted_tracks)` → adds

**UI Preview:**
```
🎵 Preview: Ultimate Workout (New Playlist)

Will create playlist with 87 unique tracks (removed 23 duplicates)
Sorted by tempo: 120-180 BPM

Source playlists:
- Workout Mix (40 tracks)
- Gym Jams (35 tracks)
- Cardio Beats (35 tracks)

[Show Duplicates Removed] [Apply] [Cancel]
```

---

### Flow 3: Split Playlist by Criteria
**User Request:** "Split my Mega Mix into two playlists: upbeat songs and chill songs"

**AI Execution:**
1. `read_playlist(mega_mix_id)` → gets 200 tracks
2. AI analyzes track characteristics (tempo, energy, danceability)
3. Splits into two lists: upbeat (120 tracks), chill (80 tracks)
4. `create_playlist("Mega Mix - Upbeat")` → upbeat_id
5. `create_playlist("Mega Mix - Chill")` → chill_id
6. `add_tracks(upbeat_id, upbeat_tracks)` → adds
7. `add_tracks(chill_id, chill_tracks)` → adds

**UI Preview:**
```
🎵 Preview: Split Mega Mix

Will create 2 new playlists:

📈 Mega Mix - Upbeat (120 tracks)
Average tempo: 135 BPM, High energy

📉 Mega Mix - Chill (80 tracks)
Average tempo: 95 BPM, Low energy

[Show Track Distribution] [Apply] [Cancel]
```

---

## Implementation Phases

### Phase 1: MCP Server Foundation (Week 1)
**Tasks:**
- [ ] Create `spotify_mcp_server.py` with basic MCP structure
- [ ] Implement read-only tools: `read_playlist`, `list_playlists`, `search_tracks`
- [ ] Test MCP server independently with MCP inspector
- [ ] Wrap existing SpotifyManager methods

**Files:**
- `spotify_mcp_server.py` (new)
- `requirements.txt` (add `mcp` package)

---

### Phase 2: MCP Integration Layer (Week 2)
**Tasks:**
- [ ] Create `mcp_manager.py` with MCPClient wrapper
- [ ] Implement OpenAI function format conversion
- [ ] Add tool execution with error handling
- [ ] Test with simple read operations

**Files:**
- `mcp_manager.py` (new)
- Test connection between Streamlit ↔ MCP server

---

### Phase 3: AI Function Calling (Week 3)
**Tasks:**
- [ ] Update `ai_manager.py` to support function calling
- [ ] Implement tool call execution loop
- [ ] Add conversation history with tool results
- [ ] Test multi-step operations (read → create → add)

**Files:**
- `ai_manager.py` (modify)
- Add async support to conversation flow

---

### Phase 4: UI Enhancements (Week 4)
**Tasks:**
- [ ] Remove playlist-specific conversation restriction
- [ ] Add multi-playlist context selector
- [ ] Enhanced preview showing cross-playlist operations
- [ ] Update conversation persistence for multi-playlist context

**Files:**
- `app.py` (modify)
- `conversation_manager.py` (modify)

---

### Phase 5: Write Operations (Week 5)
**Tasks:**
- [ ] Add MCP write tools: `create_playlist`, `add_tracks`, `remove_tracks`, `replace_playlist`
- [ ] Implement preview-before-apply for write operations
- [ ] Add rollback capability for failed operations
- [ ] Comprehensive error handling

**Files:**
- `spotify_mcp_server.py` (extend)
- `app.py` (add preview logic)

---

### Phase 6: Testing & Polish (Week 6)
**Tasks:**
- [ ] End-to-end testing of all flows
- [ ] Performance optimization (batch operations)
- [ ] Error message improvements
- [ ] Documentation updates

---

## Technical Decisions

### Why MCP Hybrid (not pure MCP)?
✅ **Keep:**
- Streamlit UI (familiar, visual, easy to use)
- Preview-before-apply safety
- User authentication flow
- Conversation persistence

✅ **Add:**
- Cross-playlist operations via MCP
- AI can read/write across playlists
- Function calling for structured operations
- Better separation of concerns

### Why Not Pure Streamlit?
❌ **Limitations:**
- Hard to extend to other interfaces (CLI, API)
- Spotify operations tightly coupled to UI
- No standard protocol for AI tool usage

### Why Not Pure MCP?
❌ **Limitations:**
- No built-in UI for previews
- User must confirm via CLI (less user-friendly)
- Harder to implement complex visual feedback

---

## File Structure After Implementation

```
Jemya/
├── app.py                      # Streamlit UI (modified)
├── spotify_mcp_server.py       # NEW: MCP server
├── mcp_manager.py              # NEW: MCP integration
├── ai_manager.py               # Modified: function calling
├── spotify_manager.py          # Keep: wrapped by MCP server
├── conversation_manager.py     # Modified: multi-playlist context
├── configuration_manager.py    # Keep: config handling
├── requirements.txt            # Add: mcp package
├── docs/
│   ├── MCP-HYBRID-DESIGN.md   # This document
│   └── MCP-API.md             # NEW: MCP tool documentation
└── tools/
    ├── test_mcp_server.py     # NEW: MCP server tests
    └── mcp_inspector.py       # NEW: MCP debugging tool
```

---

## Migration Path

### Option A: Gradual Migration (Recommended)
1. Build MCP server alongside existing code
2. Add MCP tools one-by-one
3. Test each tool independently
4. Switch AI to use MCP tools gradually
5. Keep old code as fallback

### Option B: Big Bang Migration
1. Build complete MCP server
2. Rewrite AI manager with function calling
3. Update UI for multi-playlist operations
4. Switch everything at once
5. Higher risk, faster completion

**Recommendation:** Option A - gradual migration minimizes risk

---

## Success Metrics

### Before MCP Hybrid:
- ❌ 0 cross-playlist operations supported
- ✅ Single playlist modifications work well
- ⚠️ User must manually combine playlists outside app

### After MCP Hybrid:
- ✅ Combine N playlists in one conversation
- ✅ Split playlists by criteria
- ✅ Deduplicate across playlists
- ✅ Cross-playlist search and recommendations
- ✅ Same preview-before-apply safety
- ✅ Better code separation (UI ↔ Business Logic)

---

## Security Considerations

1. **Token Management:**
   - MCP server receives token from Streamlit app
   - Token not stored in MCP server
   - Each request passes fresh token

2. **Tool Access Control:**
   - Read operations: always allowed
   - Write operations: require user confirmation in UI
   - Preview shown before any write

3. **Error Handling:**
   - Failed tool calls don't crash app
   - Clear error messages in UI
   - Rollback capability for multi-step operations

---

## Cost Analysis

### Development Cost:
- Phase 1-2: 2 weeks (foundation)
- Phase 3-4: 2 weeks (integration)
- Phase 5-6: 2 weeks (completion)
- **Total: 6 weeks**

### Operational Cost:
- Same OpenAI API costs (GPT-4o-mini: ~$0.15 per 1M input tokens)
- MCP server runs locally (no additional hosting)
- Slightly more tokens due to function calling overhead (~10-20% increase)

### Cost-Benefit:
- ✅ Enables new use cases (combine playlists)
- ✅ Better code architecture
- ✅ Easier to extend with new tools
- ✅ Opens door to CLI/API interfaces
- ⚠️ Development time investment

---

## Next Steps

1. **Review this design** - discuss any changes needed
2. **Decide on migration approach** - gradual (Option A) or big bang (Option B)
3. **Start Phase 1** - build basic MCP server with read-only tools
4. **Test independently** - verify MCP server works before integration
5. **Iterate** - add tools and features incrementally

---

## Questions for Discussion

1. Should we support real-time collaboration (multiple users editing same playlist)?
2. Do we need undo/redo capability for playlist operations?
3. Should MCP server support other music services (Apple Music, YouTube Music) in future?
4. Do we want CLI interface in addition to Streamlit UI?
5. Should we add playlist version control (track changes over time)?

---

*Document Version: 1.0*  
*Last Updated: February 4, 2026*  
*Author: GitHub Copilot*
