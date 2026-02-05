"""
AI Functions Module
Handles all OpenAI interactions for the Jemya playlist generator.
Supports both legacy mode (direct playlist suggestions) and MCP mode (function calling).
"""

import json
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

import configuration_manager as conf


class AIManager:
    """Manages AI interactions for track extraction and processing."""
    
    def __init__(self, mcp_manager=None):
        self.client = OpenAI(api_key=conf.OPENAI_API_KEY)
        self.mcp_manager = mcp_manager
        self.mcp_enabled = mcp_manager is not None    
    @staticmethod
    def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
        """Estimate token count for messages (rough approximation)
        
        OpenAI's rule of thumb: 1 token ≈ 4 characters for English text
        """
        total_chars = 0
        for msg in messages:
            if isinstance(msg.get('content'), str):
                total_chars += len(msg['content'])
            if 'tool_calls' in msg:
                # Tool calls add overhead
                total_chars += len(str(msg['tool_calls'])) * 2
        
        return total_chars // 4    
    async def generate_with_mcp(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        max_iterations: int = 5,
        max_context_tokens: int = 100000  # Leave headroom for tools and response
    ) -> Dict[str, Any]:
        """
        Generate response using MCP function calling with smart context management.
        
        Args:
            user_message: The user's request
            conversation_history: Previous conversation messages
            max_iterations: Maximum number of function call iterations
            max_context_tokens: Maximum tokens to keep in context (default: 100k)
            
        Returns:
            Dict with 'response', 'tool_calls', and 'tool_results'
        """
        if not self.mcp_enabled:
            raise ValueError("MCP manager not configured")
        
        # Get MCP tools for OpenAI
        tools = await self.mcp_manager.get_tools_for_openai()
        
        # Smart context management: Remove old tool results (they're ephemeral)
        # BUT keep ALL conversation messages for full context
        system_messages = [m for m in conversation_history if m.get("role") == "system"]
        non_system_messages = [m for m in conversation_history if m.get("role") != "system"]
        
        # Filter out old tool results - they're already incorporated in assistant responses
        # Keep ALL user/assistant messages
        cleaned = []
        for msg in non_system_messages:
            if msg.get("role") == "tool":
                # Skip old tool results (ephemeral, not needed after AI responds)
                continue
            cleaned.append(msg)
        
        # Build messages with ALL history (no message count limit)
        messages = system_messages + cleaned + [{"role": "user", "content": user_message}]
        
        # Only trim if we exceed token budget
        estimated = self.estimate_tokens(messages)
        print(f"DEBUG: Initial context ~{estimated} tokens")
        
        if estimated > max_context_tokens:
            print(f"DEBUG: Context at ~{estimated} tokens (exceeds {max_context_tokens}), trimming older messages")
            # Keep system + recent messages to fit budget
            # Start with most recent and work backwards
            trimmed = system_messages + [{"role": "user", "content": user_message}]
            for msg in reversed(cleaned):
                test_messages = system_messages + [msg] + trimmed[len(system_messages):]
                if self.estimate_tokens(test_messages) < max_context_tokens:
                    trimmed.insert(len(system_messages), msg)
                else:
                    break
            messages = trimmed
            print(f"DEBUG: Context trimmed to ~{self.estimate_tokens(messages)} tokens, kept {len(trimmed) - len(system_messages) - 1} messages")
        
        all_tool_calls = []
        all_tool_results = []
        
        for iteration in range(max_iterations):
            # Call OpenAI with tools
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            
            # Check if AI wants to call functions
            if not assistant_message.tool_calls:
                # No more function calls, return final response
                return {
                    'response': assistant_message.content,
                    'tool_calls': all_tool_calls,
                    'tool_results': all_tool_results,
                    'final_message': assistant_message
                }
            
            # Execute the tool calls
            tool_results = await self.mcp_manager.execute_tool_calls(assistant_message.tool_calls)
            
            # Track all tool calls and results
            all_tool_calls.extend(assistant_message.tool_calls)
            all_tool_results.extend(tool_results)
            
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in assistant_message.tool_calls
                ]
            })
            
            # Add tool results
            messages.extend(tool_results)
            
            # CRITICAL: After adding tool results, check context size
            # If we're approaching limits, remove older tool results
            estimated = self.estimate_tokens(messages)
            if estimated > max_context_tokens:
                print(f"DEBUG: Context at ~{estimated} tokens, removing old tool results")
                # Keep system, user messages, and only most recent tool exchange
                trimmed = []
                for msg in messages:
                    if msg.get("role") in ["system", "user"]:
                        trimmed.append(msg)
                    elif msg.get("role") == "assistant":
                        # Keep assistant messages but only the most recent tool_calls
                        if msg.get("tool_calls") and msg == messages[-2]:
                            trimmed.append(msg)  # Most recent assistant with tools
                        else:
                            # Drop tool_calls from older messages
                            trimmed.append({"role": "assistant", "content": msg.get("content", "")})
                    elif msg.get("role") == "tool":
                        # Only keep tool results from current iteration
                        if msg in tool_results:
                            trimmed.append(msg)
                
                messages = trimmed
                print(f"DEBUG: Context trimmed to ~{self.estimate_tokens(messages)} tokens")
        
        # Max iterations reached, return what we have
        return {
            'response': "Maximum iterations reached. Please try again with a simpler request.",
            'tool_calls': all_tool_calls,
            'tool_results': all_tool_results,
            'max_iterations_reached': True
        }
    
    def extract_tracks_from_ai_response(self, track_suggestions: List[str]) -> List[Dict[str, Any]]:
        """Extract the complete desired playlist from AI suggestions"""
        try:
            # Combine all AI suggestions into one prompt
            combined_suggestions = "\n".join(track_suggestions)
            
            prompt = f"""
            Please extract the complete desired playlist from the following AI suggestions and convert them to JSON format.
            Return the COMPLETE playlist as it should be after applying all changes - this means the final track order including existing tracks and any additions/removals/reorderings.
            Each track should have: track_name, artist            
            AI Suggestions:
            {combined_suggestions}
            
            Return ONLY a JSON array representing the complete final playlist order, no other text.
            Example format:
            [
                {{
                    "track_name": "First Song",
                    "artist": "Artist Name"
                }},
                {{
                    "track_name": "Second Song", 
                    "artist": "Artist Name"
                }}
            ]
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a precise JSON extractor. Extract track information and return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            response_content = response.choices[0].message.content
            print(f"DEBUG: OpenAI track extraction response: {response_content}")
            
            # Parse the JSON response
            desired_playlist = self.parse_json_from_response(response_content)
            return desired_playlist
            
        except Exception as e:
            print(f"Error extracting tracks from AI response: {e}")
            raise Exception(f"Failed to extract tracks: {str(e)}")
    
    def parse_json_from_response(self, message_content: str) -> List[Dict[str, Any]]:
        """Parse JSON data from OpenAI response, returning the complete desired playlist"""
        # Extract JSON from code blocks
        pattern = r"```(.*?)```"
        matches = re.findall(pattern, message_content, re.DOTALL)
        playlist_data = None
        
        for match in matches:
            try:
                # Remove language identifier if present (like "json")
                clean_match = re.sub(r'^(json|python|javascript)\s*\n', '', match.strip(), flags=re.IGNORECASE)
                playlist_data = json.loads(clean_match)
                break
            except json.JSONDecodeError:
                continue
        
        # If no code block found, try to parse the entire response as JSON
        if not playlist_data:
            try:
                playlist_data = json.loads(message_content)
            except json.JSONDecodeError:
                pass
        
        # Extract playlist from different formats
        tracks = []
        if isinstance(playlist_data, list):
            tracks = playlist_data
        elif isinstance(playlist_data, dict):
            if 'playlist' in playlist_data:
                tracks = playlist_data['playlist'] if isinstance(playlist_data['playlist'], list) else []
            elif 'tracks' in playlist_data:
                tracks = playlist_data['tracks'] if isinstance(playlist_data['tracks'], list) else []
        
        # Process tracks - ensure each track has required fields
        processed_tracks = []
        for track in tracks:
            if isinstance(track, dict):
                processed_track = {
                    'track_name': track.get('track_name', track.get('name', '')),
                    'artist': track.get('artist', track.get('artists', ''))
                }
                if processed_track['track_name'] and processed_track['artist']:
                    processed_tracks.append(processed_track)
        
        return processed_tracks
    
    def generate_system_message(self, has_spotify_connection: bool = False, mcp_mode: bool = False) -> str:
        """Generate system message for OpenAI chat completion"""
        
        if mcp_mode:
            # MCP mode: AI can use function calling to interact with Spotify
            base_message = (
                "You are Jemya, a playlist management assistant with access to Spotify operations through function calling.\n\n"
                "You have the following capabilities via function calls:\n"
                "• READ PLAYLISTS: Use read_playlist(playlist_id) to get tracks from any playlist\n"
                "• LIST PLAYLISTS: Use list_playlists() to see ALL user playlists (fetches everything with automatic paging)\n"
                "• SEARCH TRACKS: Use search_tracks(query) to find tracks on Spotify\n"
                "• CREATE PLAYLISTS: Use create_playlist(name, description) to create new playlists\n"
                "• ADD TRACKS: Use add_tracks(playlist_id, track_uris) to add tracks\n"
                "• REMOVE TRACKS: Use remove_tracks(playlist_id, track_uris) to remove tracks\n"
                "• REPLACE PLAYLIST: Use replace_playlist(playlist_id, track_uris) to replace all tracks\n\n"
                "Cross-Playlist Operations:\n"
                "• COMBINE: Read multiple playlists and create a new one with all tracks\n"
                "• MERGE & DEDUPLICATE: Combine playlists while removing duplicate tracks (same URI)\n"
                "• SPLIT: Analyze one playlist and create multiple playlists based on criteria (genre, mood, tempo, etc.)\n"
                "• INTELLIGENT REORDERING: Read playlist, analyze flow, and replace with optimized order\n\n"
                "Workflow:\n"
                "1. Use list_playlists() to see available playlists\n"
                "2. Filter results in your logic (by name, year, description, etc.)\n"
                "3. Use read_playlist(playlist_id) with EXACT playlist IDs from step 1\n"
                "4. Analyze tracks and plan operations\n"
                "5. Execute operations (create, add, remove, replace)\n"
                "6. Explain what you did and why\n\n"
                "CRITICAL RULES:\n"
                "• playlist_id parameters must be EXACT Spotify IDs (like '37i9dQZF1DX...'), NOT names or patterns\n"
                "• NEVER use wildcards like '2025*' or 'workout*' in playlist_id\n"
                "• To find playlists by name/year: call list_playlists(), then filter in your logic\n"
                "• Always explain your plan before executing operations\n"
                "• For write operations, clearly state what will change\n"
                "• Track URIs from read_playlist can be used directly in add/remove/replace operations\n"
                "• When combining playlists, preserve track order unless user requests reordering\n\n"
                "Example: To find '2025' playlists:\n"
                "1. Call list_playlists(limit=30) to get playlists\n"
                "2. Filter results where name contains '2025'\n"
                "3. Call read_playlist(playlist_id) for each matching playlist ID\n\n"
                "COMBINE PLAYLISTS WORKFLOW:\n"
                "When user asks to combine/merge playlists:\n"
                "1. Call list_playlists() to get all playlists\n"
                "2. Filter playlists matching user criteria (name pattern, year, etc.)\n"
                "3. Call read_playlist() for EACH playlist to combine\n"
                "4. Collect all track URIs from all playlists\n"
                "5. If user wants deduplication: Remove duplicate URIs (keep first occurrence)\n"
                "6. Call create_playlist(name, description) to create the combined playlist\n"
                "7. Call add_tracks(new_playlist_id, all_track_uris) to add all tracks\n"
                "8. Report success with playlist name, URL, and track count\n\n"
                "Example: 'Combine all 2025 playlists':\n"
                "→ list_playlists() → filter by '2025' → read_playlist() × N → create_playlist('Combined 2025') → add_tracks()"
            )
        else:
            # Legacy mode: Direct playlist suggestions (current behavior)
            base_message = (
                "You are Jemya, a playlist enrichment specialist with deep expertise in music curation and seamless track integration. "
                "Your primary role is to analyze existing playlists and intelligently weave new tracks into the existing structure, creating smooth musical transitions.\n\n"
                "Core Capabilities:\n"
                "• PLAYLIST ANALYSIS: Identify musical patterns, themes, genres, moods, energy levels, tempo, key signatures, and temporal flow\n"
                "• INTELLIGENT TRACK INSERTION: Insert new tracks at optimal positions within the existing playlist structure (between, before, or after specific tracks)\n"
                "• TRANSITION MASTERY: When placing tracks between contrasting songs, select bridging tracks that create smooth musical transitions\n"
                "• FLOW PRESERVATION: Maintain musical coherence by matching tempo, key, energy, and mood when inserting new tracks\n"
                "• CONTEXTUAL PLACEMENT: Consider each track's position relative to its neighbors for optimal listening experience\n\n"
                "Track Insertion Strategy:\n"
                "• Analyze adjacent tracks (before/after) for tempo, key, energy, mood, and genre compatibility\n"
                "• Insert tracks that complement both neighboring songs when possible\n"
                "• For contrasting adjacent tracks, add 1-3 transition tracks that bridge the musical gap smoothly\n"
                "• Consider natural breakpoints: genre shifts, energy changes, mood transitions\n"
                "• Preserve intentional contrasts while smoothing jarring transitions\n"
                "• Explain insertion logic: why each track goes in its specific position and how it enhances the flow\n\n"
                "Response Format:\n"
                "• Present the complete final playlist in the desired order\n"
                "• Show the full track list exactly as it should appear after all changes\n"
                "• Include existing tracks that should remain, in their final positions\n"
                "• Include new tracks in their optimal positions within the complete playlist\n"
                "• Exclude any tracks that should be removed\n"
                "• Explain the overall vision and flow of the final playlist"
            )
        
        if has_spotify_connection:
            base_message += " The user is connected to Spotify, so you can suggest creating playlists and provide detailed analysis of their existing collections."
        else:
            base_message += " The user is not connected to Spotify yet, so encourage them to connect their account to unlock the full potential of playlist analysis and creation."
        
        return base_message