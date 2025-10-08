"""
Spotify Library Module
Handles all Spotify API interactions for the Jemya playlist generator.
"""

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from typing import Dict, List, Optional, Tuple, Any
import conf


class SpotifyManager:
    """Manages Spotify API interactions and authentication."""
    
    def __init__(self):
        self.client_id = conf.CLIENT_ID
        self.client_secret = conf.CLIENT_SECRET
        self.redirect_uri = conf.REDIRECT_URI
        self.scope = "user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state"
    
    def get_spotify_oauth(self) -> SpotifyOAuth:
        """Get configured SpotifyOAuth instance"""
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope
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
                
                playlists = []
                offset = 0
                limit = 50
                
                while True:
                    print(f"DEBUG: Fetching playlists offset={offset}, limit={limit}")
                    response = sp.current_user_playlists(offset=offset, limit=limit)
                    print(f"DEBUG: Response type: {type(response)}, has items: {'items' in response if response else False}")
                    
                    if response and 'items' in response:
                        playlists.extend(response['items'])
                        print(f"DEBUG: Added {len(response['items'])} playlists, total: {len(playlists)}")
                        
                        if len(response['items']) < limit:
                            break
                        offset += limit
                    else:
                        break
                
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
    
    def search_and_validate_tracks(self, tracks: List[Dict[str, Any]], sp: spotipy.Spotify) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Search for tracks on Spotify and return URIs with validation info"""
        track_results = []
        tracks_not_found = []
        
        for track_data in tracks:
            if not isinstance(track_data, dict):
                continue
                
            track_name = track_data.get('track_name', '').strip()
            artist = track_data.get('artist', '').strip()
            
            if not track_name or not artist:
                continue
            
            # Search for the track on Spotify
            query = f"track:{track_name} artist:{artist}"
            try:
                results = sp.search(q=query, type='track', limit=1)
                if results['tracks']['items']:
                    found_track = results['tracks']['items'][0]
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
            except Exception as e:
                print(f"Error searching for track '{track_name}' by '{artist}': {e}")
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
        """Generate comprehensive search strategies for track and artist"""
        # Clean up track name - remove artist name if it's redundantly included
        clean_track_name = track_name
        if artist_name.lower() in track_name.lower():
            # Remove artist name from track name if present
            words_to_remove = artist_name.split(',')[0].strip().split()
            for word in words_to_remove:
                if len(word) > 2:  # Only remove meaningful words
                    clean_track_name = clean_track_name.replace(word, '').strip()
                    clean_track_name = ' '.join(clean_track_name.split())  # Clean extra spaces
        
        # Clean up artist name
        clean_artist_name = artist_name
        # Handle common AI mistakes
        artist_corrections = {
            'skrjabin': 'scriabin',
            'skryabin': 'scriabin',
            'the beatles, violin': 'the beatles',
            'to life': '',  # This is often wrong for Hava Nagila
        }
        
        for wrong, correct in artist_corrections.items():
            if wrong in clean_artist_name.lower():
                clean_artist_name = correct if correct else clean_artist_name
        
        # Generate comprehensive search strategies
        search_strategies = [
            # Strategy 1: Exact search with quotes (original)
            f"track:\"{track_name}\" artist:\"{artist_name}\"",
            # Strategy 2: Exact search with quotes (cleaned)
            f"track:\"{clean_track_name}\" artist:\"{clean_artist_name}\"" if clean_track_name != track_name or clean_artist_name != artist_name else None,
            # Strategy 3: Search without quotes (original)
            f"track:{track_name} artist:{artist_name}",
            # Strategy 4: Search without quotes (cleaned)
            f"track:{clean_track_name} artist:{clean_artist_name}" if clean_track_name != track_name or clean_artist_name != artist_name else None,
            # Strategy 5: Simple combined search (original)
            f"\"{track_name}\" \"{artist_name}\"",
            # Strategy 6: Simple combined search (cleaned) 
            f"\"{clean_track_name}\" \"{clean_artist_name}\"" if clean_track_name != track_name or clean_artist_name != artist_name else None,
            # Strategy 7: Just track and artist names (original)
            f"{track_name} {artist_name}",
            # Strategy 8: Just track and artist names (cleaned)
            f"{clean_track_name} {clean_artist_name}" if clean_track_name != track_name or clean_artist_name != artist_name else None,
            # Strategy 9: Try with first artist only if comma-separated (original)
            f"{track_name} {artist_name.split(',')[0].strip()}" if ',' in artist_name else None,
            # Strategy 10: Try with first artist only if comma-separated (cleaned)
            f"{clean_track_name} {clean_artist_name.split(',')[0].strip()}" if ',' in clean_artist_name and (clean_track_name != track_name or clean_artist_name != artist_name) else None,
            # Strategy 11: Just track name (for hard to find tracks)
            f"\"{track_name}\"",
            # Strategy 12: Just cleaned track name
            f"\"{clean_track_name}\"" if clean_track_name != track_name else None,
            # Strategy 13: Track name with common classical terms
            f"{track_name} classical" if any(word in track_name.lower() for word in ['concerto', 'sonata', 'prelude', 'nocturne', 'gymnopedie']) else None,
            # Strategy 14: Track name with jazz terms
            f"{track_name} jazz" if any(word in artist_name.lower() for word in ['django', 'louis', 'armstrong', 'reinhardt']) else None,
            # Strategy 15: Final fallback - just original track name without quotes (broad search)
            f"{track_name}",
            # Strategy 16: Final fallback - just cleaned track name without quotes
            f"{clean_track_name}" if clean_track_name != track_name else None,
            # Strategy 17: Track name without common suffixes
            track_name.replace(" (Instrumental)", "").replace(" - Instrumental", "").strip() if any(suffix in track_name for suffix in [" (Instrumental)", " - Instrumental"]) else None,
            # Strategy 18: Cleaned track name without common suffixes
            clean_track_name.replace(" (Instrumental)", "").replace(" - Instrumental", "").strip() if clean_track_name != track_name and any(suffix in clean_track_name for suffix in [" (Instrumental)", " - Instrumental"]) else None
        ]
        
        # Remove None strategies and duplicates
        return list(dict.fromkeys([s for s in search_strategies if s is not None]))
    
    def search_track_with_flexible_matching(self, sp: spotipy.Spotify, track_name: str, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search for a track using comprehensive strategies and flexible matching"""
        search_strategies = self.generate_search_strategies(track_name, artist_name)
        
        # Pre-calculate cleaned values for matching
        clean_track_name = track_name
        if artist_name.lower() in track_name.lower():
            words_to_remove = artist_name.split(',')[0].strip().split()
            for word in words_to_remove:
                if len(word) > 2:
                    clean_track_name = clean_track_name.replace(word, '').strip()
                    clean_track_name = ' '.join(clean_track_name.split())
        
        clean_artist_name = artist_name
        artist_corrections = {
            'skrjabin': 'scriabin',
            'skryabin': 'scriabin',
            'the beatles, violin': 'the beatles',
            'to life': '',
        }
        for wrong, correct in artist_corrections.items():
            if wrong in clean_artist_name.lower():
                clean_artist_name = correct if correct else clean_artist_name
        
        try:
            for search_query in search_strategies:
                results = sp.search(q=search_query, type='track', limit=5)
                
                if results['tracks']['items']:
                    # Look for best match among results
                    for candidate in results['tracks']['items']:
                        candidate_name = candidate['name'].lower()
                        candidate_artists = ' '.join([artist['name'].lower() for artist in candidate['artists']])
                        
                        # More flexible matching for track names
                        original_name_lower = track_name.lower()
                        clean_name_lower = clean_track_name.lower()
                        
                        name_match = (
                            # Exact matches
                            original_name_lower in candidate_name or 
                            candidate_name in original_name_lower or
                            clean_name_lower in candidate_name or
                            candidate_name in clean_name_lower or
                            # Partial matches for long classical titles (3+ letter words)
                            any(word in candidate_name for word in original_name_lower.split() if len(word) > 3) or
                            any(word in candidate_name for word in clean_name_lower.split() if len(word) > 3) or
                            # Remove common prefixes/suffixes and try again
                            any(word in candidate_name for word in original_name_lower.replace(' (instrumental)', '').replace(' - ', ' ').split() if len(word) > 3)
                        )
                        
                        # More flexible matching for artists
                        original_artist_lower = artist_name.lower()
                        clean_artist_lower = clean_artist_name.lower()
                        
                        artist_match = (
                            # Direct matches
                            original_artist_lower in candidate_artists or
                            candidate_artists in original_artist_lower or
                            clean_artist_lower in candidate_artists or
                            candidate_artists in clean_artist_lower or
                            # Partial artist matches
                            any(artist.strip().lower() in candidate_artists 
                                for artist in original_artist_lower.split(',') if len(artist.strip()) > 2) or
                            any(artist.strip().lower() in candidate_artists 
                                for artist in clean_artist_lower.split(',') if len(artist.strip()) > 2) or
                            # For problematic artists, just accept if track name is very close
                            (name_match and any(bad_artist in original_artist_lower for bad_artist in ['to life', 'midnight string', 'violin'])) or
                            # For fallback track-only searches, be more flexible with artist matching
                            (search_query == track_name or search_query == clean_track_name or 
                             search_query == track_name.replace(" (Instrumental)", "").replace(" - Instrumental", "").strip() or
                             search_query == clean_track_name.replace(" (Instrumental)", "").replace(" - Instrumental", "").strip())
                        )
                        
                        if name_match and artist_match:
                            return candidate
            
            return None
            
        except Exception as e:
            print(f"ERROR: Failed searching for track '{track_name} - {artist_name}': {e}")
            return None

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