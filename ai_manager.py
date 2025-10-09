"""
AI Functions Module
Handles all OpenAI interactions for the Jemya playlist generator.
"""

from openai import OpenAI
import json
import re
from typing import List, Dict, Any
import config as conf  # Smart configuration loader


class AIManager:
    """Manages AI interactions for track extraction and processing."""
    
    def __init__(self):
        self.client = OpenAI(api_key=conf.OPENAI_API_KEY)
    
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
                model="gpt-4o",
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
    
    def generate_system_message(self, has_spotify_connection: bool = False) -> str:
        """Generate system message for OpenAI chat completion"""
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