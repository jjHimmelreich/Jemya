"""
Spotify Library Module
Handles all Spotify API interactions for the Jemya playlist generator.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import spotipy
import streamlit as st
from openai import OpenAI
from spotipy.oauth2 import SpotifyOAuth

import configuration_manager as conf


class SpotifyManager:
    """Manages Spotify API interactions and authentication."""
    
    def __init__(self):
        self.client_id = conf.SPOTIFY_CLIENT_ID
        self.client_secret = conf.SPOTIFY_CLIENT_SECRET
        self.redirect_uri = conf.SPOTIFY_REDIRECT_URI
        self.scope = "user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state"
        self.openai_client = OpenAI(api_key=conf.OPENAI_API_KEY)
        # Use a persistent cache file for token storage
        self.cache_path = ".spotify_token_cache"
    
    def get_spotify_oauth(self) -> SpotifyOAuth:
        """Get configured SpotifyOAuth instance"""
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=self.cache_path  # Enable persistent file caching
        )
    
    def refresh_spotify_token_if_needed(self) -> Optional[Dict[str, Any]]:
        """Refresh Spotify token if expired and save to session state"""
        if not st.session_state.token_info:
            return None
            
        token_info = st.session_state.token_info
        
        # Check if token exists and has expiration info
        if not isinstance(token_info, dict) or 'expires_at' not in token_info:
            return token_info
        
        current_time = time.time()
        # Only refresh if token is actually expired (with small buffer)
        if current_time > (token_info['expires_at'] - 30):
            try:
                print("DEBUG: Token expired, refreshing...")
                sp_oauth = self.get_spotify_oauth()
                refreshed_token = sp_oauth.refresh_access_token(token_info['refresh_token'])
                # Save refreshed token back to session state
                st.session_state.token_info = refreshed_token
                print("DEBUG: Token refreshed and saved to session")
                return refreshed_token
            except Exception as e:
                print(f"ERROR: Token refresh failed: {e}")
                return None
        else:
            print("DEBUG: Token still valid, no refresh needed")
            return token_info
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get Spotify user information"""
        token_info = self.refresh_spotify_token_if_needed()
        if token_info and isinstance(token_info, dict) and 'access_token' in token_info:
            try:
                sp = spotipy.Spotify(auth=token_info['access_token'])
                return sp.current_user()
            except Exception as e:
                print(f"Error getting user info: {e}")
        return None
    
    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Tuple[bool, str, Optional[str]]:
        """Create a new playlist for the user
        
        Returns:
            Tuple of (success: bool, message: str, playlist_id: Optional[str])
        """
        token_info = self.refresh_spotify_token_if_needed()
        if not token_info or not isinstance(token_info, dict) or 'access_token' not in token_info:
            return False, "Not authenticated with Spotify", None
        
        try:
            sp = spotipy.Spotify(auth=token_info['access_token'])
            user_id = sp.current_user()['id']
            
            # Create the playlist
            playlist = sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description
            )
            
            playlist_id = playlist['id']
            print(f"DEBUG: Created playlist '{name}' with ID: {playlist_id}")
            
            return True, f"Playlist '{name}' created successfully!", playlist_id
            
        except Exception as e:
            print(f"ERROR: Failed to create playlist: {e}")
            return False, f"Failed to create playlist: {str(e)}", None
    
    @staticmethod
    def fetch_all_playlists_from_spotify(sp: spotipy.Spotify) -> List[Dict[str, Any]]:
        """Fetch all playlists from Spotify API (no session state dependencies)
        
        Args:
            sp: Authenticated Spotify client
            
        Returns:
            List of raw playlist items from Spotify API
        """
        playlists = []
        offset = 0
        limit = 50
        
        while True:
            response = sp.current_user_playlists(offset=offset, limit=limit)
            
            if not response or 'items' not in response:
                break
            
            playlists.extend(response['items'])
            
            # Stop if we got fewer items than requested (end of list)
            if len(response['items']) < limit:
                break
            
            offset += limit
        
        return playlists
    
    def get_user_playlists(self) -> List[Dict[str, Any]]:
        """Get user's Spotify playlists with caching to prevent constant refetching"""
        # Check if playlists are already cached and still valid
        if ('cached_playlists' in st.session_state and 
            'playlists_cache_time' in st.session_state and
            time.time() - st.session_state.playlists_cache_time < 300):  # 5 minutes cache
            print("DEBUG: Using cached playlists")
            return st.session_state.cached_playlists
        
        print(f"DEBUG: get_user_playlists called - fetching fresh data")
        token_info = self.refresh_spotify_token_if_needed()
        if token_info and isinstance(token_info, dict) and 'access_token' in token_info:
            try:
                print("DEBUG: Valid token, creating Spotify client...")
                sp = spotipy.Spotify(auth=token_info['access_token'])
                print("DEBUG: Created Spotify client, fetching playlists...")
                
                # Use shared helper method
                playlists = self.fetch_all_playlists_from_spotify(sp)
                
                print(f"DEBUG: Returning {len(playlists)} playlists (cached)")
                # Cache the results
                st.session_state.cached_playlists = playlists
                st.session_state.playlists_cache_time = time.time()
                return playlists
            except Exception as e:
                print(f"Error in get_user_playlists: {e}")
        print("DEBUG: Invalid token or no token, returning empty list")
        return []
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get all tracks from a specific playlist"""
        print(f"DEBUG: get_playlist_tracks called for playlist {playlist_id}")
        token_info = self.refresh_spotify_token_if_needed()
        if token_info and isinstance(token_info, dict) and 'access_token' in token_info:
            try:
                print("DEBUG: Valid token, creating Spotify client for tracks...")
                sp = spotipy.Spotify(auth=token_info['access_token'])
                
                tracks = []
                offset = 0
                limit = 100
                
                while True:
                    print(f"DEBUG: Fetching tracks offset={offset}, limit={limit}")
                    response = sp.playlist_tracks(playlist_id, offset=offset, limit=limit)
                    print(f"DEBUG: Tracks response type: {type(response)}, has items: {'items' in response if response else False}")
                    
                    if response and 'items' in response:
                        for item in response['items']:
                            if item and item.get('track'):
                                track = item['track']
                                if track and track.get('name'):  # Only add valid tracks
                                    # Extract track information
                                    external_urls = track.get('external_urls', {})
                                    track_info = {
                                        'id': track.get('id', ''),
                                        'name': track.get('name', 'Unknown'),
                                        'artists': ', '.join([artist.get('name', 'Unknown') for artist in track.get('artists', [])]),
                                        'album': track.get('album', {}).get('name', 'Unknown'),
                                        'duration_ms': track.get('duration_ms', 0),
                                        'popularity': track.get('popularity', 0),
                                        'explicit': track.get('explicit', False),
                                        'spotify_url': external_urls.get('spotify', '')
                                    }
                                    tracks.append(track_info)
                        
                        print(f"DEBUG: Added {len(response['items'])} track items, total valid tracks: {len(tracks)}")
                        
                        if len(response['items']) < limit:
                            break
                        offset += limit
                    else:
                        break
                
                print(f"DEBUG: Returning {len(tracks)} tracks")
                return tracks
            except Exception as e:
                print(f"Error in get_playlist_tracks: {e}")
                return []
        print("DEBUG: Invalid token for tracks, returning empty list")
        return []
    
    def get_current_playlist_track_uris(self, playlist_id: str, sp: spotipy.Spotify) -> set:
        """Get URIs of all tracks currently in the playlist"""
        try:
            track_uris = []
            offset = 0
            limit = 100
            
            while True:
                response = sp.playlist_tracks(playlist_id, offset=offset, limit=limit, fields="items.track.uri,next")
                if response and 'items' in response:
                    for item in response['items']:
                        if item and item.get('track') and item['track'].get('uri'):
                            track_uris.append(item['track']['uri'])
                    
                    if len(response['items']) < limit:
                        break
                    offset += limit
                else:
                    break
            
            return set(track_uris)  # Return as set for fast lookup
        except Exception as e:
            print(f"Error getting current playlist tracks: {e}")
            return set()
    
    def search_and_validate_tracks(self, tracks: List[Dict[str, Any]], sp: spotipy.Spotify, use_ai_batch: bool = False) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Search for tracks on Spotify and return URIs with validation info"""
        track_results = []
        tracks_not_found = []
        
        if use_ai_batch:
            # Prepare batch requests for AI-enhanced search
            batch_requests = []
            track_metadata = []
            
            for track_data in tracks:
                if not isinstance(track_data, dict):
                    continue
                    
                track_name = track_data.get('track_name', '').strip()
                artist = track_data.get('artist', '').strip()
                
                if not track_name or not artist:
                    continue
                
                batch_requests.append({
                    'track_name': track_name,
                    'artist_name': artist
                })
                track_metadata.append(track_data)
            
            # Use batch AI search
            if batch_requests:
                print(f"DEBUG: Using AI batch search for {len(batch_requests)} tracks")
                batch_results = self.search_tracks_batch_with_ai_fallback(sp, batch_requests)
                
                for i, found_track in enumerate(batch_results):
                    original_data = track_metadata[i]
                    track_name = batch_requests[i]['track_name']
                    artist = batch_requests[i]['artist_name']
                    
                    if found_track:
                        track_results.append({
                            'uri': found_track['uri'],
                            'found_name': found_track['name'],
                            'found_artist': ', '.join([artist['name'] for artist in found_track['artists']]),
                            'found_album': found_track['album']['name'],
                            'duration_ms': found_track['duration_ms'],
                            'spotify_url': found_track['external_urls']['spotify'],
                            'position_instruction': original_data.get('position_instruction', 'at the end'),
                            'order_index': original_data.get('order_index', 0)
                        })
                    else:
                        tracks_not_found.append(f"{track_name} - {artist}")
        else:
            # Original search logic (first result from first successful strategy)
            for track_data in tracks:
                if not isinstance(track_data, dict):
                    continue
                    
                track_name = track_data.get('track_name', '').strip()
                artist = track_data.get('artist', '').strip()
                
                if not track_name or not artist:
                    continue
                
                # Use the simplified search (first result from first successful strategy)
                found_track = self.search_track_with_flexible_matching(sp, track_name, artist)
                
                if found_track:
                    track_results.append({
                        'uri': found_track['uri'],
                        'found_name': found_track['name'],
                        'found_artist': ', '.join([artist['name'] for artist in found_track['artists']]),
                        'found_album': found_track['album']['name'],
                        'duration_ms': found_track['duration_ms'],
                        'spotify_url': found_track['external_urls']['spotify'],
                        'position_instruction': track_data.get('position_instruction', 'at the end'),
                        'order_index': track_data.get('order_index', 0)
                    })
                else:
                    tracks_not_found.append(f"{track_name} - {artist}")
        
        return track_results, tracks_not_found
    
    def apply_track_positioning(self, playlist_id: str, sp: spotipy.Spotify, new_tracks_with_positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply tracks to playlist respecting position instructions"""
        if not new_tracks_with_positions:
            return []
        
        # Get current playlist length for positioning calculations
        try:
            playlist_info = sp.playlist(playlist_id, fields="tracks.total")
            current_playlist_length = playlist_info['tracks']['total']
        except Exception as e:
            print(f"Error getting playlist info: {e}")
            current_playlist_length = 0
        
        # Group tracks by positioning strategy
        tracks_for_end = []  # Default: add at the end
        tracks_with_specific_positions = []  # Need specific positioning
        
        for track in new_tracks_with_positions:
            position_instruction = track.get('position_instruction', 'at the end').lower()
            
            if position_instruction == 'at the end' or 'end' in position_instruction:
                tracks_for_end.append(track)
            else:
                tracks_with_specific_positions.append(track)
        
        user_id = sp.current_user()['id']
        added_tracks = []
        
        # First, add tracks that go at the end (simpler operation)
        if tracks_for_end:
            track_uris = [track['uri'] for track in tracks_for_end]
            sp.user_playlist_add_tracks(user_id, playlist_id, track_uris)
            added_tracks.extend(tracks_for_end)
            print(f"DEBUG: Added {len(tracks_for_end)} tracks at the end")
        
        # Then handle specific positioning (more complex)
        for track in tracks_with_specific_positions:
            position_instruction = track.get('position_instruction', 'at the end').lower()
            
            try:
                # Add track at end first, then we'll move it
                sp.user_playlist_add_tracks(user_id, playlist_id, [track['uri']])
                added_tracks.append(track)
                
                if 'after' in position_instruction and 'track' in position_instruction:
                    # Parse position like "after track 3"
                    import re
                    match = re.search(r'after track (\d+)', position_instruction)
                    if match:
                        target_position = int(match.group(1))
                        # Move track to desired position
                        # Spotify uses 0-based indexing
                        sp.playlist_reorder_items(playlist_id, current_playlist_length, target_position)
                
                elif 'before' in position_instruction and 'track' in position_instruction:
                    # Parse position like "before track 5"
                    import re
                    match = re.search(r'before track (\d+)', position_instruction)
                    if match:
                        target_position = int(match.group(1)) - 1  # Convert to 0-based and place before
                        sp.playlist_reorder_items(playlist_id, current_playlist_length, target_position)
                
                elif 'position' in position_instruction:
                    # Parse position like "at position 7"
                    import re
                    match = re.search(r'position (\d+)', position_instruction)
                    if match:
                        target_position = int(match.group(1)) - 1  # Convert to 0-based
                        sp.playlist_reorder_items(playlist_id, current_playlist_length, target_position)
                
                current_playlist_length += 1
                print(f"DEBUG: Added '{track['found_name']}' at position {position_instruction}")
                
            except Exception as e:
                print(f"Error positioning track '{track['found_name']}': {e}")
                # Fallback to adding at the end
                try:
                    sp.user_playlist_add_tracks(user_id, playlist_id, [track['uri']])
                    added_tracks.append(track)
                except Exception as e2:
                    print(f"Error adding track '{track['found_name']}' at end: {e2}")
        
        return added_tracks
    
    def align_playlist_to_desired_state(self, playlist_id: str, sp: spotipy.Spotify, desired_playlist: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Align the current playlist to match the desired state from AI"""
        try:
            # Get current playlist tracks
            current_tracks = []
            offset = 0
            limit = 100
            
            while True:
                results = sp.playlist_tracks(playlist_id, offset=offset, limit=limit, fields='items(track(id,name,artists(name),uri)),next')
                
                if not results or 'items' not in results:
                    break
                
                for item in results['items']:
                    if item and 'track' in item and item['track']:
                        track = item['track']
                        current_tracks.append({
                            'uri': track['uri'],
                            'name': track['name'],
                            'artists': ', '.join([artist['name'] for artist in track.get('artists', [])]),
                            'id': track['id']
                        })
                
                if not results.get('next'):
                    break
                
                offset += limit
            
            print(f"DEBUG: Current playlist has {len(current_tracks)} tracks")
            print(f"DEBUG: Desired playlist has {len(desired_playlist)} tracks")
            
            # Clear the current playlist
            if current_tracks:
                current_uris = [track['uri'] for track in current_tracks]
                # Remove in batches of 100
                for i in range(0, len(current_uris), 100):
                    batch = current_uris[i:i+100]
                    sp.user_playlist_remove_all_occurrences_of_tracks(
                        sp.current_user()['id'], 
                        playlist_id, 
                        batch
                    )
                print(f"DEBUG: Cleared {len(current_tracks)} tracks from playlist")
            
            # Search and add desired tracks in order
            added_tracks = []
            not_found_tracks = []
            
            for track in desired_playlist:
                track_name = track.get('track_name', '')
                artist_name = track.get('artist', '')
                
                if not track_name or not artist_name:
                    continue
                
                # Use the centralized search function
                found_track = self.search_track_with_flexible_matching(sp, track_name, artist_name)
                
                if found_track:
                    track_uri = found_track['uri']
                    
                    # Add track to playlist
                    sp.user_playlist_add_tracks(sp.current_user()['id'], playlist_id, [track_uri])
                    added_tracks.append({
                        'name': found_track['name'],
                        'artist': ', '.join([artist['name'] for artist in found_track['artists']]),
                        'uri': track_uri
                    })
                    print(f"DEBUG: Added track: {found_track['name']} - {', '.join([artist['name'] for artist in found_track['artists']])}")
                else:
                    not_found_tracks.append(f"{track_name} - {artist_name}")
                    print(f"DEBUG: Track not found: {track_name} - {artist_name}")
            
            return {
                'added_count': len(added_tracks),
                'removed_count': len(current_tracks),
                'not_found_count': len(not_found_tracks),
                'added_tracks': added_tracks,
                'not_found_tracks': not_found_tracks
            }
            
        except Exception as e:
            print(f"ERROR: Failed to align playlist: {e}")
            return {
                'added_count': 0,
                'removed_count': 0,
                'not_found_count': 0,
                'added_tracks': [],
                'not_found_tracks': []
            }
    
    def find_and_remove_tracks(self, playlist_id: str, sp: spotipy.Spotify, tracks_to_remove: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find and remove tracks from playlist based on track name and artist"""
        if not tracks_to_remove:
            return []
        
        removed_tracks = []
        
        try:
            # Get current playlist tracks
            current_tracks = []
            offset = 0
            limit = 100
            
            while True:
                results = sp.playlist_tracks(playlist_id, offset=offset, limit=limit, fields='items(track(id,name,artists(name),uri)),next')
                
                if not results or 'items' not in results:
                    break
                
                for item in results['items']:
                    if item and 'track' in item and item['track']:
                        track = item['track']
                        current_tracks.append({
                            'uri': track['uri'],
                            'name': track['name'],
                            'artists': ', '.join([artist['name'] for artist in track.get('artists', [])]),
                            'id': track['id']
                        })
                
                if not results.get('next'):
                    break
                
                offset += limit
            
            print(f"DEBUG: Found {len(current_tracks)} tracks in playlist for removal checking")
            
            # Match tracks to remove with current playlist tracks
            tracks_uris_to_remove = []
            
            for remove_track in tracks_to_remove:
                remove_name = remove_track.get('track_name', '').lower().strip()
                remove_artist = remove_track.get('artist', '').lower().strip()
                
                # Find matching tracks in playlist
                for current_track in current_tracks:
                    current_name = current_track['name'].lower().strip()
                    current_artists = current_track['artists'].lower().strip()
                    
                    # Check for exact or close matches
                    name_match = remove_name in current_name or current_name in remove_name
                    artist_match = remove_artist in current_artists or current_artists in remove_artist
                    
                    if name_match and artist_match:
                        tracks_uris_to_remove.append(current_track['uri'])
                        removed_tracks.append({
                            'name': current_track['name'],
                            'artist': current_track['artists'],
                            'uri': current_track['uri']
                        })
                        print(f"DEBUG: Matched track for removal: {current_track['name']} - {current_track['artists']}")
                        break
            
            # Remove tracks from playlist
            if tracks_uris_to_remove:
                # Remove duplicates while preserving order
                unique_uris = list(dict.fromkeys(tracks_uris_to_remove))
                
                # Spotify API accepts up to 100 tracks per request
                for i in range(0, len(unique_uris), 100):
                    batch = unique_uris[i:i+100]
                    sp.user_playlist_remove_all_occurrences_of_tracks(
                        sp.current_user()['id'], 
                        playlist_id, 
                        batch
                    )
                    print(f"DEBUG: Removed batch of {len(batch)} tracks from playlist")
            
            return removed_tracks
            
        except Exception as e:
            print(f"Error removing tracks from playlist: {e}")
            return []
    
    def generate_search_strategies(self, track_name: str, artist_name: str) -> List[str]:
        """Generate search strategies for track and artist"""
        # Generate search strategies
        search_strategies = [
            # Strategy 1: Exact search with quotes
            f"track:\"{track_name}\" artist:\"{artist_name}\"",
            # Strategy 2: Search without quotes
            f"track:{track_name} artist:{artist_name}",
            # Strategy 3: Simple combined search
            f"\"{track_name}\" \"{artist_name}\"",
            # Strategy 4: Just track and artist names
            f"{track_name} {artist_name}",
            # Strategy 5: Try with first artist only if comma-separated
            f"{track_name} {artist_name.split(',')[0].strip()}" if ',' in artist_name else None,
            # Strategy 6: Just track name (for hard to find tracks)
            f"\"{track_name}\"",
            # Strategy 7: Final fallback - just track name without quotes
            f"{track_name}",
        ]
        
        # Remove None strategies and duplicates
        return list(dict.fromkeys([s for s in search_strategies if s is not None]))
    
    def search_track_with_flexible_matching(self, sp: spotipy.Spotify, track_name: str, artist_name: str, use_ai_fallback: bool = False) -> Optional[Dict[str, Any]]:
        """Search for a track using strategies - return first result from first successful strategy"""
        search_strategies = self.generate_search_strategies(track_name, artist_name)
        
        try:
            print(f"DEBUG: Searching for '{track_name}' by '{artist_name}' using {len(search_strategies)} strategies")
            for i, search_query in enumerate(search_strategies):
                print(f"DEBUG: Strategy {i+1}: '{search_query}'")
                results = sp.search(q=search_query, type='track', limit=10)
                
                if results['tracks']['items']:
                    print(f"DEBUG: Strategy {i+1} returned {len(results['tracks']['items'])} results")
                    # Simply return the first result from the first successful strategy
                    first_result = results['tracks']['items'][0]
                    artists_str = ', '.join([artist['name'] for artist in first_result['artists']])
                    print(f"DEBUG: Using first result: '{first_result['name']}' by '{artists_str}'")
                    return first_result
                else:
                    print(f"DEBUG: Strategy {i+1} returned no results")
            
            print(f"DEBUG: No results found for '{track_name}' by '{artist_name}' after trying {len(search_strategies)} strategies")
            
            # If no results found and AI fallback is enabled, try the enhanced search
            if use_ai_fallback:
                print(f"DEBUG: Trying AI fallback search...")
                return self.search_track_with_ai_fallback(sp, track_name, artist_name)
            
            return None
            
        except (spotipy.SpotifyException, ValueError, KeyError) as e:
            print(f"ERROR: Failed searching for track '{track_name} - {artist_name}': {e}")
            return None

    def ai_select_best_matches_batch(self, track_requests: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Use AI to select the best matching tracks for multiple requests in one call"""
        if not track_requests:
            return {}
        
        try:
            # Prepare the batch request for AI
            batch_prompt = "You are an expert music librarian helping match music tracks. For each target track, I'll provide a list of candidate tracks found from Spotify searches.\n\n"
            
            request_data = {}
            for i, request in enumerate(track_requests, 1):
                target_track = request['target_track']
                target_artist = request['target_artist']
                candidates = request['candidates']
                request_key = f"{target_track}|{target_artist}"
                request_data[request_key] = candidates
                
                # Add to batch prompt
                batch_prompt += f"TARGET TRACK {i}: '{target_track}' by '{target_artist}'\n"
                batch_prompt += f"CANDIDATES:\n"
                
                for j, track in enumerate(candidates, 1):
                    artists_str = ', '.join([artist['name'] for artist in track['artists']])
                    batch_prompt += f"  {j}. '{track['name']}' by '{artists_str}'\n"
                
                batch_prompt += "\n"
            
            batch_prompt += """For each target track, analyze which candidate is the closest match. Consider:
1. Track title similarity (accounting for variations in naming, opus numbers, key signatures, etc.)
2. Artist similarity (main composer/performer match)  
3. Musical work identity (same piece of music, even with different recording details)

Return your response in this exact JSON format:
{
  "1": 2,
  "2": 1,
  "3": 0
}

Where the key is the target track number (1, 2, 3, etc.) and the value is the best matching candidate number (1-N) or 0 if no good match exists.

JSON Response:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert music librarian helping match music tracks. Return only valid JSON."},
                    {"role": "user", "content": batch_prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            print(f"DEBUG: AI batch response: {result}")
            
            # Parse the AI response
            try:
                selections = json.loads(result)
                results = {}
                
                for i, request in enumerate(track_requests, 1):
                    target_track = request['target_track']
                    target_artist = request['target_artist']
                    candidates = request['candidates']
                    request_key = f"{target_track}|{target_artist}"
                    
                    selected_index = int(selections.get(str(i), 0))
                    
                    if 1 <= selected_index <= len(candidates):
                        selected_track = candidates[selected_index - 1]
                        artists_str = ', '.join([artist['name'] for artist in selected_track['artists']])
                        print(f"DEBUG: AI selected #{selected_index} for '{target_track}': '{selected_track['name']}' by '{artists_str}'")
                        results[request_key] = selected_track
                    elif selected_index == 0:
                        print(f"DEBUG: AI found no good match for '{target_track}'")
                        results[request_key] = None
                    else:
                        print(f"DEBUG: AI returned invalid index {selected_index} for '{target_track}', using first candidate")
                        results[request_key] = candidates[0] if candidates else None
                
                return results
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"DEBUG: Failed to parse AI batch response: {e}")
                # Fallback to first candidate for each request
                results = {}
                for request in track_requests:
                    target_track = request['target_track']
                    target_artist = request['target_artist']
                    candidates = request['candidates']
                    request_key = f"{target_track}|{target_artist}"
                    results[request_key] = candidates[0] if candidates else None
                return results
            
        except Exception as e:
            print(f"ERROR: AI batch selection failed: {e}")
            # Fallback to first candidate for each request
            results = {}
            for request in track_requests:
                target_track = request['target_track']
                target_artist = request['target_artist']
                candidates = request['candidates']
                request_key = f"{target_track}|{target_artist}"
                results[request_key] = candidates[0] if candidates else None
            return results

    def search_tracks_batch_with_ai_fallback(self, sp: spotipy.Spotify, track_requests: List[Dict[str, str]]) -> List[Optional[Dict[str, Any]]]:
        """Search for multiple tracks and use AI to select best matches in batch"""
        if not track_requests:
            return []
        
        print(f"DEBUG: Batch searching {len(track_requests)} tracks with AI fallback")
        
        # First, collect all candidates for all tracks
        all_track_data = []
        for request in track_requests:
            track_name = request['track_name']
            artist_name = request['artist_name']
            
            search_strategies = self.generate_search_strategies(track_name, artist_name)
            all_candidates = []
            
            try:
                print(f"DEBUG: Searching '{track_name}' by '{artist_name}' using {len(search_strategies)} strategies")
                
                # Collect all candidates from all strategies
                for i, search_query in enumerate(search_strategies):
                    results = sp.search(q=search_query, type='track', limit=10)
                    
                    if results['tracks']['items']:
                        print(f"DEBUG: Strategy {i+1} returned {len(results['tracks']['items'])} results")
                        
                        # Add unique tracks to candidates (avoid duplicates)
                        for track in results['tracks']['items']:
                            track_id = track['id']
                            if not any(candidate['id'] == track_id for candidate in all_candidates):
                                all_candidates.append(track)
                
                print(f"DEBUG: Found {len(all_candidates)} unique candidates for '{track_name}'")
                
                all_track_data.append({
                    'target_track': track_name,
                    'target_artist': artist_name,
                    'candidates': all_candidates
                })
                
            except (spotipy.SpotifyException, ValueError, KeyError) as e:
                print(f"ERROR: Search failed for '{track_name}': {e}")
                all_track_data.append({
                    'target_track': track_name,
                    'target_artist': artist_name,
                    'candidates': []
                })
        
        # Filter out tracks that have no candidates
        tracks_needing_ai = [data for data in all_track_data if data['candidates']]
        
        # Use AI to select best matches for all tracks in one call
        ai_results = {}
        if tracks_needing_ai:
            print(f"DEBUG: Using AI to select best matches for {len(tracks_needing_ai)} tracks")
            ai_results = self.ai_select_best_matches_batch(tracks_needing_ai)
        
        # Build final results list
        final_results = []
        for data in all_track_data:
            target_track = data['target_track']
            target_artist = data['target_artist']
            candidates = data['candidates']
            request_key = f"{target_track}|{target_artist}"
            
            if not candidates:
                final_results.append(None)
            elif len(candidates) == 1:
                # Single candidate, use it
                selected = candidates[0]
                artists_str = ', '.join([artist['name'] for artist in selected['artists']])
                print(f"DEBUG: Single candidate for '{target_track}': '{selected['name']}' by '{artists_str}'")
                final_results.append(selected)
            else:
                # Multiple candidates, use AI result
                ai_selected = ai_results.get(request_key)
                final_results.append(ai_selected)
        
        return final_results

    def search_track_with_ai_fallback(self, sp: spotipy.Spotify, track_name: str, artist_name: str) -> Optional[Dict[str, Any]]:
        """Enhanced search that collects all candidates and uses AI to select the best match"""
        search_strategies = self.generate_search_strategies(track_name, artist_name)
        all_candidates = []
        
        try:
            print(f"DEBUG: Enhanced search for '{track_name}' by '{artist_name}' using {len(search_strategies)} strategies")
            
            # Collect all candidates from all strategies
            for i, search_query in enumerate(search_strategies):
                print(f"DEBUG: Strategy {i+1}: '{search_query}'")
                results = sp.search(q=search_query, type='track', limit=10)
                
                if results['tracks']['items']:
                    print(f"DEBUG: Strategy {i+1} returned {len(results['tracks']['items'])} results")
                    
                    # Add unique tracks to candidates (avoid duplicates)
                    for track in results['tracks']['items']:
                        # Check if we already have this track
                        track_id = track['id']
                        if not any(candidate['id'] == track_id for candidate in all_candidates):
                            all_candidates.append(track)
                else:
                    print(f"DEBUG: Strategy {i+1} returned no results")
            
            if not all_candidates:
                print(f"DEBUG: No candidates found for '{track_name}' by '{artist_name}'")
                return None
            
            print(f"DEBUG: Found {len(all_candidates)} unique candidates across all strategies")
            
            # If we have candidates, use AI to select the best match
            if len(all_candidates) == 1:
                # Only one candidate, return it
                selected = all_candidates[0]
                artists_str = ', '.join([artist['name'] for artist in selected['artists']])
                print(f"DEBUG: Single candidate: '{selected['name']}' by '{artists_str}'")
                return selected
            else:
                # Multiple candidates, use batch AI with single track
                batch_request = [{
                    'target_track': track_name,
                    'target_artist': artist_name,
                    'candidates': all_candidates
                }]
                ai_results = self.ai_select_best_matches_batch(batch_request)
                request_key = f"{track_name}|{artist_name}"
                return ai_results.get(request_key)
            
        except (spotipy.SpotifyException, ValueError, KeyError) as e:
            print(f"ERROR: Enhanced search failed for '{track_name} - {artist_name}': {e}")
            return None

    def _flexible_name_match(self, original_name, candidate_name):
        """Generalized flexible matching for track names"""
        def normalize_track_name(name):
            """Normalize track names for flexible comparison"""
            if not name:
                return ""
            normalized = name.lower()
            
            # Remove common music metadata patterns
            # Opus numbers, BWV, K. numbers, RV numbers
            normalized = re.sub(r'\b(op\.?\s*\d+[a-z]?(\s*no\.?\s*\d+)?)\b', 'opus', normalized)
            normalized = re.sub(r'\b(bwv|rv|k\.?\s*\d+)\b', 'catalog', normalized)
            
            # Key signatures and musical terms
            normalized = re.sub(r'\b(in\s+[a-g][#b]?\s*(major|minor))\b', 'key', normalized)
            normalized = re.sub(r'\b(adagio|allegro|andante|presto|largo|moderato|vivace|alla\s+marcia)\b', '', normalized)
            
            # Movement numbers (Roman numerals)
            normalized = re.sub(r'\b(i{1,3}v?|v|vi{1,3}|ix|x)\.?\s*', '', normalized)
            
            # Remove collection numbers at start (like "10 Preludes" -> "Preludes")
            # But preserve important numbers like "No. 5", "Op. 23"
            normalized = re.sub(r'^\d+\s+(?!no\.?\s*\d)', '', normalized)
            
            # Remove version indicators
            normalized = re.sub(r'\b(version|ver|live|remaster|remastered|remix|edit)\b', '', normalized)
            
            # Remove year patterns
            normalized = re.sub(r'\b(19|20)\d{2}\b', '', normalized)
            
            # Remove common suffixes/prefixes
            normalized = re.sub(r'\b(feat\.?|ft\.?|featuring|with|the|a|an)\b', '', normalized)
            
            # Clean up quotes, punctuation, and extra spaces
            normalized = re.sub(r'[^\w\s]', '', normalized)
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            
            return normalized
        
        # Early check for numbered pieces before normalization
        # Extract "No." numbers specifically (these identify specific pieces)
        original_piece_numbers = set(re.findall(r'\bno\.?\s*(\d+)\b', original_name.lower()))
        candidate_piece_numbers = set(re.findall(r'\bno\.?\s*(\d+)\b', candidate_name.lower()))
        
        # If both have piece numbers and they're different, likely different pieces
        if original_piece_numbers and candidate_piece_numbers:
            if not original_piece_numbers.intersection(candidate_piece_numbers):
                # Check if the base title (without numbers) is similar
                original_base = re.sub(r'\b(?:no\.?\s*)?\d+\b|\b(?:op\.?\s*)?\d+\b', '', original_name.lower()).strip()
                candidate_base = re.sub(r'\b(?:no\.?\s*)?\d+\b|\b(?:op\.?\s*)?\d+\b', '', candidate_name.lower()).strip()
                
                # If base titles are very similar, these are different numbered pieces
                if original_base and candidate_base:
                    original_base_words = set(re.findall(r'\b\w+\b', original_base))
                    candidate_base_words = set(re.findall(r'\b\w+\b', candidate_base))
                    if len(original_base_words.intersection(candidate_base_words)) >= 1:
                        return False  # Same type of piece but different numbers
        
        original_norm = normalize_track_name(original_name)
        candidate_norm = normalize_track_name(candidate_name)
        
        # Try normalized substring matching
        if original_norm in candidate_norm or candidate_norm in original_norm:
            return True
            
        # Word-based matching for better flexibility
        original_words = set(word for word in original_norm.split() if len(word) > 2)
        candidate_words = set(word for word in candidate_norm.split() if len(word) > 2)
        
        # If at least 60% of significant original words are found in candidate
        if len(original_words) > 0:
            common_words = original_words.intersection(candidate_words)
            match_ratio = len(common_words) / len(original_words)
            return match_ratio >= 0.6
            
        return False

    @staticmethod
    def format_time_human_readable(time_ms: int) -> str:
        """Convert milliseconds to human-readable time format (e.g., '1h 23m', '3m 45s', '30s')"""
        if time_ms == 0:
            return "0s"
        
        total_minutes = time_ms // 60000
        seconds = (time_ms % 60000) // 1000
        
        if total_minutes >= 60:
            hours = total_minutes // 60
            remaining_minutes = total_minutes % 60
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            else:
                return f"{hours}h"
        else:
            if seconds > 0:
                return f"{total_minutes}m {seconds}s"
            else:
                return f"{total_minutes}m"