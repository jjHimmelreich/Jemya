import streamlit as st
from openai import OpenAI
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import json
import os
import base64
import conf

# Spotify Configuration
CLIENT_ID = conf.SPOTIFY_CLIENT_ID
CLIENT_SECRET = conf.SPOTIFY_CLIENT_SECRET
REDIRECT_URI = conf.SPOTIFY_REDIRECT_URI

OPENAI_API_KEY = conf.OPENAI_API_KEY

# Initialize OpenAI client with API key from secrets
client = OpenAI(api_key=OPENAI_API_KEY)

# Spotify OAuth setup
def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state"
    )

def refresh_token_if_needed():
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
            sp_oauth = get_spotify_oauth()
            refreshed_token = sp_oauth.refresh_access_token(token_info['refresh_token'])
            # Save refreshed token back to session state
            st.session_state.token_info = refreshed_token
            st.session_state.last_token_check = current_time
            print("DEBUG: Token refreshed and saved to session")
            return refreshed_token
        except Exception as e:
            print(f"ERROR: Failed to refresh token: {e}")
            return token_info
    else:
        # Only print debug message once per session or every 5 minutes
        if not hasattr(st.session_state, 'last_token_check') or (current_time - st.session_state.last_token_check) > 300:
            print("DEBUG: Token still valid, no refresh needed")
            st.session_state.last_token_check = current_time
        return token_info

def get_user_info():
    """Get Spotify user information"""
    token_info = refresh_token_if_needed()
    if token_info and isinstance(token_info, dict) and 'access_token' in token_info:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_info = sp.current_user()
        return user_info
    return None

def get_user_playlists():
    """Get user's Spotify playlists with caching to prevent constant refetching"""
    # Check if playlists are already cached and still valid
    if ('cached_playlists' in st.session_state and 
        'playlists_cache_time' in st.session_state and
        time.time() - st.session_state.playlists_cache_time < 300):  # Cache for 5 minutes
        print("DEBUG: Using cached playlists")
        return st.session_state.cached_playlists
    
    print(f"DEBUG: get_user_playlists called - fetching fresh data")
    token_info = refresh_token_if_needed()
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
            
            # Cache the results
            st.session_state.cached_playlists = playlists
            st.session_state.playlists_cache_time = time.time()
            print(f"DEBUG: Returning {len(playlists)} playlists (cached)")
            return playlists
        except Exception as e:
            print(f"Error in get_user_playlists: {e}")
            return []
    print("DEBUG: Invalid token or no token, returning empty list")
    return []

def get_playlist_tracks(playlist_id):
    """Get all tracks from a specific playlist"""
    print(f"DEBUG: get_playlist_tracks called for playlist {playlist_id}")
    token_info = refresh_token_if_needed()
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

def format_time_human_readable(time_ms):
    """Convert milliseconds to human-readable time format (e.g., '1h 23m', '3m 45s', '30s')"""
    if time_ms == 0:
        return "0s"
    
    total_minutes = time_ms // 60000
    seconds = (time_ms % 60000) // 1000
    
    if total_minutes >= 60:
        # For durations over 1 hour, don't show seconds
        hours = total_minutes // 60
        remaining_minutes = total_minutes % 60
        
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours}h"
    else:
        # For durations under 1 hour, show seconds
        if seconds > 0:
            return f"{total_minutes}m {seconds}s"
        elif total_minutes > 0:
            return f"{total_minutes}m"
        else:
            return f"{seconds}s"

def apply_playlist_changes(playlist_id, track_suggestions):
    """Apply AI-suggested changes to a Spotify playlist"""
    token_info = refresh_token_if_needed()
    if not token_info or not isinstance(token_info, dict) or 'access_token' not in token_info:
        return False, "No valid Spotify authentication"
    
    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        
        # Use OpenAI to extract structured track data from suggestions
        combined_suggestions = "\n".join(track_suggestions)
        
        # Create a structured prompt to extract track information
        extract_prompt = combined_suggestions + """

Please analyze the conversation above and extract all the suggested tracks for the Spotify playlist. 
Please provide me with the tracks in a structured format.
Please format the response as a JSON object so it can be easily parsed with Python.
It should be an objects list where the objects are in the form of { "track_name": "", "artist": "" }.
Only include actual song titles and artist names, not descriptions or explanations.
"""

        try:
            # Call OpenAI to extract structured track data
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts track information from playlist suggestions."},
                    {"role": "user", "content": extract_prompt}
                ]
            )
            
            message_content = response.choices[0].message.content
            print(f"DEBUG: OpenAI track extraction response: {message_content}")
            
            # Parse the JSON response (similar to backend/openai_lib.py approach)
            import re
            import json
            
            # Extract JSON from code blocks
            pattern = r"```(.*?)```"
            matches = re.findall(pattern, message_content, re.DOTALL)
            playlist_data = None
            
            for match in matches:
                try:
                    # Clean up the JSON string
                    json_str = match.replace('json', '').strip()
                    playlist_data = json.loads(json_str)
                    break
                except json.JSONDecodeError:
                    continue
            
            # If no code block found, try to parse the entire response as JSON
            if not playlist_data:
                try:
                    playlist_data = json.loads(message_content)
                except json.JSONDecodeError:
                    return False, "Could not parse track suggestions from AI response"
            
            # Extract tracks from the parsed data
            tracks = []
            if isinstance(playlist_data, list):
                tracks = playlist_data
            elif isinstance(playlist_data, dict) and 'playlist' in playlist_data:
                tracks = playlist_data['playlist']
            elif isinstance(playlist_data, dict) and 'tracks' in playlist_data:
                tracks = playlist_data['tracks']
            
            if not tracks:
                return False, "No tracks found in AI response"
                
        except Exception as e:
            print(f"ERROR: OpenAI extraction failed: {e}")
            return False, f"Failed to extract tracks from AI suggestions: {str(e)}"
        
        # Now search for each track on Spotify
        track_uris = []
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
                    track_uri = results['tracks']['items'][0]['uri']
                    track_uris.append(track_uri)
                else:
                    tracks_not_found.append(f"{track_name} - {artist}")
            except Exception as e:
                print(f"Error searching for track {track_name} - {artist}: {e}")
                tracks_not_found.append(f"{track_name} - {artist}")
        
        if track_uris:
            # Add tracks to the playlist (using same method as backend)
            user_id = sp.current_user()['id']
            sp.user_playlist_add_tracks(user_id, playlist_id, track_uris)
            success_msg = f"Successfully added {len(track_uris)} tracks to playlist"
            if tracks_not_found:
                success_msg += f". Could not find {len(tracks_not_found)} tracks: {', '.join(tracks_not_found[:3])}"
                if len(tracks_not_found) > 3:
                    success_msg += f" and {len(tracks_not_found) - 3} more"
            return True, success_msg
        else:
            return False, "No tracks found to add to playlist"
            
    except Exception as e:
        print(f"Error applying playlist changes: {e}")
        return False, f"Error applying changes: {str(e)}"

# Conversation management functions
def get_conversation_file_path(user_id, playlist_id):
    """Generate file path for conversation storage"""
    conversations_dir = "conversations"
    if not os.path.exists(conversations_dir):
        os.makedirs(conversations_dir)
    return os.path.join(conversations_dir, f"{user_id}_{playlist_id}.json")

def get_session_file_path(user_id):
    """Generate file path for session storage"""
    conversations_dir = "conversations"
    if not os.path.exists(conversations_dir):
        os.makedirs(conversations_dir)
    return os.path.join(conversations_dir, f"{user_id}_session.json")

def save_user_session(user_id, current_playlist_id=None, current_playlist_name=None):
    """Save user's last session state"""
    try:
        file_path = get_session_file_path(user_id)
        session_data = {
            "user_id": user_id,
            "last_playlist_id": current_playlist_id,
            "last_playlist_name": current_playlist_name,
            "last_login_time": time.time()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        print(f"DEBUG: Saved session for user {user_id}, last playlist: {current_playlist_name}")
    except Exception as e:
        print(f"ERROR: Failed to save user session: {e}")

def load_user_session(user_id):
    """Load user's last session state"""
    try:
        file_path = get_session_file_path(user_id)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            print(f"DEBUG: Loaded session for user {user_id}, last playlist: {session_data.get('last_playlist_name')}")
            return session_data
    except Exception as e:
        print(f"ERROR: Failed to load user session: {e}")
    return None

def save_conversation(user_id, playlist_id, messages, playlist_snapshot=None):
    """Save conversation to file with optional playlist snapshot"""
    try:
        file_path = get_conversation_file_path(user_id, playlist_id)
        
        # Try to load existing data to preserve playlist snapshot
        existing_snapshot = None
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    existing_snapshot = existing_data.get('playlist_snapshot')
            except Exception as e:
                print(f"DEBUG: Could not load existing snapshot: {e}")
        
        conversation_data = {
            "user_id": user_id,
            "playlist_id": playlist_id,
            "messages": messages,
            "last_updated": time.time()
        }
        
        # Use provided snapshot, or preserve existing one
        if playlist_snapshot:
            conversation_data["playlist_snapshot"] = playlist_snapshot
            print(f"DEBUG: Saving with new playlist snapshot")
        elif existing_snapshot:
            conversation_data["playlist_snapshot"] = existing_snapshot
            print(f"DEBUG: Preserving existing playlist snapshot")
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conversation_data, f, ensure_ascii=False, indent=2)
        print(f"DEBUG: Saved conversation for user {user_id}, playlist {playlist_id}")
    except Exception as e:
        print(f"ERROR: Failed to save conversation: {e}")

def get_playlist_snapshot(playlist, tracks):
    """Create a snapshot of playlist for change detection"""
    return {
        "track_count": len(tracks),
        "track_ids": [track.get('id', '') for track in tracks if track.get('id')],
        "playlist_name": playlist.get('name', ''),
        "last_modified": playlist.get('snapshot_id', ''),  # Spotify's snapshot_id changes when playlist is modified
        "total_duration": sum(track.get('duration_ms', 0) for track in tracks)
    }

def has_playlist_changed(user_id, playlist_id, current_playlist, current_tracks):
    """Check if playlist content has changed since last save"""
    try:
        file_path = get_conversation_file_path(user_id, playlist_id)
        if not os.path.exists(file_path):
            return True  # No previous data, consider it changed
            
        with open(file_path, 'r', encoding='utf-8') as f:
            conversation_data = json.load(f)
            
        saved_snapshot = conversation_data.get('playlist_snapshot')
        if not saved_snapshot:
            return True  # No snapshot saved, consider it changed
            
        current_snapshot = get_playlist_snapshot(current_playlist, current_tracks)
        
        print(f"DEBUG: Comparing playlist snapshots for {playlist_id}:")
        print(f"DEBUG: Saved snapshot: {saved_snapshot}")
        print(f"DEBUG: Current snapshot: {current_snapshot}")
        
        # Compare key indicators of playlist changes
        track_count_changed = saved_snapshot.get('track_count') != current_snapshot.get('track_count')
        snapshot_id_changed = saved_snapshot.get('last_modified') != current_snapshot.get('last_modified')
        name_changed = saved_snapshot.get('playlist_name') != current_snapshot.get('playlist_name')
        duration_changed = saved_snapshot.get('total_duration') != current_snapshot.get('total_duration')
        
        changed = track_count_changed or snapshot_id_changed or name_changed or duration_changed
        
        if changed:
            print(f"DEBUG: Playlist {playlist_id} has changed:")
            print(f"  - Track count: {saved_snapshot.get('track_count')} -> {current_snapshot.get('track_count')} (changed: {track_count_changed})")
            print(f"  - Snapshot ID: {saved_snapshot.get('last_modified')} -> {current_snapshot.get('last_modified')} (changed: {snapshot_id_changed})")
            print(f"  - Name: {saved_snapshot.get('playlist_name')} -> {current_snapshot.get('playlist_name')} (changed: {name_changed})")
            print(f"  - Duration: {saved_snapshot.get('total_duration')} -> {current_snapshot.get('total_duration')} (changed: {duration_changed})")
        else:
            print(f"DEBUG: Playlist {playlist_id} unchanged since last load")
            
        return changed
        
    except Exception as e:
        print(f"ERROR: Failed to check playlist changes: {e}")
        return True  # If we can't compare, assume it changed

def load_conversation(user_id, playlist_id):
    """Load conversation from file"""
    try:
        file_path = get_conversation_file_path(user_id, playlist_id)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                conversation_data = json.load(f)
            print(f"DEBUG: Loaded conversation for user {user_id}, playlist {playlist_id} with {len(conversation_data.get('messages', []))} messages")
            return conversation_data.get('messages', [])
    except Exception as e:
        print(f"ERROR: Failed to load conversation: {e}")
    return []

def has_conversation_changed(user_id, playlist_id, current_messages):
    """Check if current conversation has changed from last saved version"""
    try:
        saved_messages = load_conversation(user_id, playlist_id)
        # Compare message count and content
        if len(saved_messages) != len(current_messages):
            return True
        
        # Compare each message
        for saved_msg, current_msg in zip(saved_messages, current_messages):
            if (saved_msg.get('role') != current_msg.get('role') or 
                saved_msg.get('content') != current_msg.get('content')):
                return True
        
        return False
    except Exception as e:
        print(f"DEBUG: Error checking conversation changes: {e}")
        return True  # If we can't compare, assume it changed to be safe

def switch_to_playlist_conversation(user_id, playlist_id, playlist_name):
    """Switch to a specific playlist conversation"""
    # Save current conversation if there's an active playlist and it has changed
    if 'current_playlist_id' in st.session_state and st.session_state.current_playlist_id:
        current_user_id = st.session_state.get('current_user_id')
        if current_user_id and has_conversation_changed(current_user_id, st.session_state.current_playlist_id, st.session_state.messages):
            save_conversation(current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
            print(f"DEBUG: Saved changed conversation for playlist {st.session_state.current_playlist_id}")
        elif current_user_id:
            print(f"DEBUG: No changes detected, skipping save for playlist {st.session_state.current_playlist_id}")
    
    # Load conversation for the new playlist
    messages = load_conversation(user_id, playlist_id)
    
    # Update session state
    st.session_state.messages = messages
    st.session_state.current_playlist_id = playlist_id
    st.session_state.current_playlist_name = playlist_name
    st.session_state.current_user_id = user_id
    
    # Save the user's session state
    save_user_session(user_id, playlist_id, playlist_name)
    
    # Add system and welcome messages if this is a new conversation
    if not messages:
        # Add system message for playlist enrichment specialist
        system_message = ("You are Jemya, a playlist enrichment specialist with deep expertise in music curation and seamless track integration. Your primary role is to analyze existing playlists and intelligently weave new tracks into the existing structure, creating smooth musical transitions.\n\n"
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
                         "• Present the enhanced playlist with original track numbers preserved\n"
                         "• Mark new tracks as 'ADDED' with insertion reasoning\n"
                         "• Use format: 'ADDED after track X: [Song] - [Artist] (bridges tempo from X to Y)'\n"
                         "• Explain transition logic for each insertion\n"
                         "• Highlight how additions improve overall playlist flow and listening experience")
        
        st.session_state.messages.append({
            "role": "system",
            "content": system_message
        })
        
        # Add welcome message
        welcome_message = f"🎵 **Analyzing playlist: {playlist_name}**\n\nI'm ready to intelligently enrich this playlist! I can analyze track-to-track transitions, insert new songs at optimal positions within your existing structure, and create smooth musical bridges between contrasting tracks. I'll explain exactly where each new track should go and why it improves the flow. What would you like me to enhance?"
        st.session_state.messages.append({
            "role": "assistant",
            "content": welcome_message
        })
    
    print(f"DEBUG: Switched to conversation for playlist '{playlist_name}' ({playlist_id})")

st.set_page_config(page_title="Jemya - Playlist Generator", page_icon="🎵")
#st.title("Jemya - Playlist Generator")

# Add CSS to remove link underlines and improve button alignment
st.markdown("""
<style>
    .sidebar .element-container a {
        text-decoration: none !important;
    }
    .sidebar a {
        text-decoration: none !important;
    }
    a {
        text-decoration: none !important;
    }
    /* Align sidebar buttons to the left */
    .sidebar .stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
    }
    .sidebar .stButton {
        width: 100% !important;
    }
    /* Improve checkbox and button alignment */
    .sidebar .stCheckbox {
        margin-bottom: 0 !important;
    }
    .sidebar .stCheckbox > label {
        font-size: 14px !important;
    }
</style>
""", unsafe_allow_html=True)

# Load Spotify icon as base64
def load_spotify_icon():
    try:
        with open("static/spotify.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"Error loading Spotify icon: {e}")
        return ""

if "spotify_icon_b64" not in st.session_state:
    st.session_state.spotify_icon_b64 = load_spotify_icon()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "token_info" not in st.session_state:
    st.session_state.token_info = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "auto_scroll" not in st.session_state:
    st.session_state.auto_scroll = False
if "current_playlist_id" not in st.session_state:
    st.session_state.current_playlist_id = None
if "current_playlist_name" not in st.session_state:
    st.session_state.current_playlist_name = None
if "current_user_id" not in st.session_state:
    st.session_state.current_user_id = None

# Sidebar for Spotify functionality
st.sidebar.title("Jemya - AI Playlist Generator")

# Handle OAuth callback
if 'code' in st.query_params:
    code = st.query_params['code']
    sp_oauth = get_spotify_oauth()
    try:
        # Use get_cached_token instead of get_access_token with as_dict=True
        token_info = sp_oauth.get_cached_token()
        if not token_info:
            token_info = sp_oauth.get_access_token(code)
            if isinstance(token_info, str):
                # If it's a string, convert to dict format expected by our code
                token_info = {'access_token': token_info}
        
        st.session_state.token_info = token_info
        # Don't call get_user_info() here as it creates a loop - let the sidebar handle it
        st.success("Successfully logged in to Spotify!")
        # Clear the code parameter and rerun
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Error during Spotify login: {str(e)}")

# Spotify login/logout section
if st.session_state.token_info is None:
    st.sidebar.markdown("Connect your Spotify account to create and manage playlists.")
    
    if st.sidebar.button("🔗 Login with Spotify", type="primary"):
        sp_oauth = get_spotify_oauth()
        auth_url = sp_oauth.get_authorize_url()
        st.sidebar.markdown(f"[Click here to authorize with Spotify]({auth_url})")
        st.sidebar.markdown("After authorization, you'll be redirected back to this app.")
else:
    # User is logged in
    user_info = st.session_state.user_info
    
    # Get user info if not available yet
    if not user_info:
        user_info = get_user_info()
        if user_info:
            st.session_state.user_info = user_info
            
            # Load last session when user first logs in
            user_id = user_info.get('id')
            if user_id:
                last_session = load_user_session(user_id)
                if last_session and last_session.get('last_playlist_id'):
                    playlist_id = last_session.get('last_playlist_id')
                    playlist_name = last_session.get('last_playlist_name', 'Unknown Playlist')
                    
                    # Load the last conversation without showing the loading message
                    print(f"DEBUG: Restoring last session - playlist: {playlist_name}")
                    messages = load_conversation(user_id, playlist_id)
                    st.session_state.messages = messages
                    st.session_state.current_playlist_id = playlist_id
                    st.session_state.current_playlist_name = playlist_name
                    st.session_state.current_user_id = user_id
                    
                    #st.sidebar.info(f"🔄 Restored your last session: **{playlist_name}**")
    
    if user_info:
        st.sidebar.success(f"{user_info.get('display_name', 'User')}!")
        #st.sidebar.write(f"**Followers:** {user_info.get('followers', {}).get('total', 0)}")
        
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            # Save current session before logging out
            if st.session_state.current_user_id and st.session_state.current_playlist_id:
                save_user_session(st.session_state.current_user_id, 
                                st.session_state.current_playlist_id, 
                                st.session_state.current_playlist_name)
                # Also save the current conversation
                if has_conversation_changed(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages):
                    save_conversation(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
            
            st.session_state.token_info = None
            st.session_state.user_info = None
            st.session_state.current_playlist_id = None
            st.session_state.current_playlist_name = None
            st.session_state.current_user_id = None
            st.session_state.messages = []
            st.rerun()
    

    # Show playlists
    st.sidebar.markdown("---")
    st.sidebar.subheader("📚 Your Playlists")
    
    # Add controls on the same line - checkbox and reload button
    col1, col2 = st.sidebar.columns([3, 2])
    
    with col1:
        # Checkbox to filter playlists
        show_only_mine = st.checkbox("Created by me", key="filter_my_playlists", value=True, help="Show only playlists created by you")
    
    with col2:
        # Add reload playlists button for debugging
        if st.button("🔄 Reload", help="Clear cache and refresh playlist data", key="reload_playlists"):
            # Clear the playlist cache to force refresh
            if 'cached_playlists' in st.session_state:
                del st.session_state.cached_playlists
            if 'playlists_cache_time' in st.session_state:
                del st.session_state.playlists_cache_time
            st.sidebar.info("Reloading playlists...")
            st.rerun()
    
    try:
        playlists = get_user_playlists()
        
        if playlists:
            # Get current user ID for filtering
            current_user_id = st.session_state.user_info.get('id') if st.session_state.user_info else None
            
            # Filter by "Created by me" first if checkbox is checked
            original_count = len(playlists)
            if show_only_mine and current_user_id:
                playlists = [p for p in playlists if isinstance(p, dict) and 
                           p.get('owner', {}).get('id') == current_user_id]
            
            # Show playlist count with filtering info
            if show_only_mine and current_user_id:
                st.sidebar.write(f"**{len(playlists)} of {original_count} playlists** (created by you)")
            else:
                st.sidebar.write(f"**{len(playlists)} playlists** (grouped by creator)")
            
            # Add search filter for playlists and creators
            search_term = st.sidebar.text_input("🔍 Search playlists & creators:", placeholder="Type to filter...")
            
            # Filter playlists based on search (search both playlist names and creator names)
            filtered_playlists = playlists
            if search_term:
                search_lower = search_term.lower()
                filtered_playlists = []
                for p in playlists:
                    if not isinstance(p, dict):
                        continue
                    
                    # Check playlist name
                    playlist_matches = search_lower in p.get('name', '').lower()
                    
                    # Check creator name
                    creator_matches = False
                    owner_data = p.get('owner', {})
                    if isinstance(owner_data, dict):
                        creator_name = owner_data.get('display_name', '')
                        if creator_name:
                            creator_matches = search_lower in creator_name.lower()
                    
                    # Include if either playlist name or creator name matches
                    if playlist_matches or creator_matches:
                        filtered_playlists.append(p)
            
            # Group playlists by creator
            creators_dict = {}
            for playlist in filtered_playlists:
                if not isinstance(playlist, dict):
                    continue
                
                # Extract creator information
                owner_data = playlist.get('owner', {})
                if isinstance(owner_data, dict):
                    creator_name = owner_data.get('display_name', 'Unknown')
                    creator_id = owner_data.get('id', '')
                    creator_external_urls = owner_data.get('external_urls', {})
                    creator_spotify_url = creator_external_urls.get('spotify', '') if isinstance(creator_external_urls, dict) else ''
                else:
                    creator_name = 'Unknown'
                    creator_id = ''
                    creator_spotify_url = ''
                
                # Use creator name as key, only show ID if no display name
                if creator_name and creator_name != 'Unknown':
                    creator_key = creator_name
                else:
                    creator_key = f"@{creator_id}" if creator_id else 'Unknown'
                
                if creator_key not in creators_dict:
                    creators_dict[creator_key] = {
                        'playlists': [],
                        'creator_info': {
                            'name': creator_name,
                            'id': creator_id,
                            'spotify_url': creator_spotify_url
                        }
                    }
                creators_dict[creator_key]['playlists'].append(playlist)
            
            # Sort creators alphabetically
            sorted_creators = sorted(creators_dict.keys())
            
            # Display playlists grouped by creator
            st.sidebar.markdown("---")
            
            for creator in sorted_creators:
                creator_data = creators_dict[creator]
                creator_playlists = creator_data['playlists']
                creator_info = creator_data['creator_info']
                
                # Sort playlists within each creator group alphabetically
                creator_playlists.sort(key=lambda x: x.get('name', '').lower())
                
                # Show creator section header with clickable link
                creator_spotify_url = creator_info['spotify_url']
                creator_id = creator_info['id']
                
                # Use provided Spotify URL or construct one from user ID
                if creator_spotify_url:
                    profile_url = creator_spotify_url
                elif creator_id:
                    profile_url = f"https://open.spotify.com/user/{creator_id}"
                else:
                    profile_url = None
                
                if profile_url:
                    st.sidebar.markdown(f"### 👤 [{creator}]({profile_url})")
                else:
                    st.sidebar.markdown(f"### 👤 {creator}")
                st.sidebar.markdown(f"*{len(creator_playlists)} playlist{'s' if len(creator_playlists) != 1 else ''}*")
                
                # Display playlists for this creator
                for playlist in creator_playlists:
                    # Safely extract playlist data with proper error handling
                    if not isinstance(playlist, dict):
                        continue
                        
                    playlist_name = playlist.get('name', 'Unknown Playlist')
                    playlist_id = playlist.get('id', '')
                    
                    # Handle tracks count safely
                    tracks_data = playlist.get('tracks', {})
                    track_count = tracks_data.get('total', 0) if isinstance(tracks_data, dict) else 0
                    
                    # Handle external URLs safely
                    external_urls = playlist.get('external_urls', {})
                    playlist_url = external_urls.get('spotify', '') if isinstance(external_urls, dict) else ''
                    
                    # Truncate long playlist names and create tooltip
                    max_name_length = 25
                    display_name = playlist_name
                    if len(playlist_name) > max_name_length:
                        display_name = playlist_name[:max_name_length] + "..."
                    
                    # Create compact one-line display with columns
                    col1, col2 = st.sidebar.columns([1, 4])
                    
                    with col1:
                        # Spotify link to open playlist in Spotify
                        if playlist_url:
                            st.markdown(f'<a href="{playlist_url}" target="_blank" title="Open in Spotify"><img src="data:image/png;base64,{st.session_state.get("spotify_icon_b64", "")}" style="vertical-align: middle;"></a>', unsafe_allow_html=True)
                        else:
                            st.markdown('<img src="data:image/png;base64,{}" width="20" height="20" style="vertical-align: middle; opacity: 0.5;" title="Spotify link not available">'.format(st.session_state.get("spotify_icon_b64", "")), unsafe_allow_html=True)
                    
                    with col2:
                        # Make playlist name clickable to load into conversation
                        button_label = f"{display_name} ({track_count})"
                        tooltip_text = f"Click to load '{playlist_name}' into conversation" if len(playlist_name) > max_name_length else f"Click to load playlist into conversation"
                        
                        if st.button(button_label, key=f"load_{playlist_id}", help=tooltip_text, type="secondary", use_container_width=True):
                            # Get current user info for conversation management
                            if not st.session_state.user_info:
                                st.session_state.user_info = get_user_info()
                            
                            user_id = st.session_state.user_info.get('id') if st.session_state.user_info else 'unknown'
                            
                            # Switch to this playlist's conversation
                            switch_to_playlist_conversation(user_id, playlist_id, playlist_name)
                            
                            # Show loading message
                            with st.sidebar:
                                with st.spinner(f"Loading tracks from '{playlist_name}'..."):
                                    tracks = get_playlist_tracks(playlist_id)
                            
                            if tracks:
                                # Check if playlist content has changed before adding to conversation
                                if has_playlist_changed(user_id, playlist_id, playlist, tracks):
                                    # Extract playlist owner information
                                    owner_data = playlist.get('owner', {})
                                    if isinstance(owner_data, dict):
                                        owner_name = owner_data.get('display_name', 'Unknown')
                                        owner_id = owner_data.get('id', '')
                                    else:
                                        owner_name = 'Unknown'
                                        owner_id = ''
                                    
                                    # Check if it's a public playlist
                                    is_public = playlist.get('public', False)
                                    
                                    # Create formatted table of tracks with creator info
                                    tracks_table = f"## 🎵 {playlist_name}\n\n"
                                    tracks_table += f"**Created by:** {owner_name}"
                                    # Only show user ID if no display name exists
                                    if not owner_name or owner_name == 'Unknown':
                                        if owner_id:
                                            tracks_table += f" (@{owner_id})"
                                    tracks_table += f" • **{len(tracks)} tracks** • {'Public' if is_public else 'Private'}\n\n"
                                    tracks_table += "| # | Track | Artist | Album | Duration | Start Time |\n"
                                    tracks_table += "|---|-------|--------|-------|----------|------------|\n"
                                    
                                    cumulative_time_ms = 0
                                    for i, track in enumerate(tracks, 1):
                                        # Format start time using the helper function
                                        start_time_str = format_time_human_readable(cumulative_time_ms)
                                        
                                        # Get current track duration and format it
                                        duration_ms = track.get('duration_ms', 0)
                                        duration_str = format_time_human_readable(duration_ms)
                                        
                                        # Truncate long names for table readability
                                        full_track_name = track.get('name', 'Unknown')
                                        track_name = full_track_name[:40]
                                        if len(full_track_name) > 40:
                                            track_name += "..."
                                        
                                        # Create clickable link if Spotify URL exists
                                        spotify_url = track.get('spotify_url', '')
                                        if spotify_url:
                                            track_name_display = f"[{track_name}]({spotify_url})"
                                        else:
                                            track_name_display = track_name
                                        
                                        artist_name = track.get('artists', 'Unknown')[:30]
                                        if len(track.get('artists', '')) > 30:
                                            artist_name += "..."
                                        
                                        album_name = track.get('album', 'Unknown')[:30]
                                        if len(track.get('album', '')) > 30:
                                            album_name += "..."
                                        
                                        tracks_table += f"| {i} | {track_name_display} | {artist_name} | {album_name} | {duration_str} | {start_time_str} |\n"
                                        
                                        # Add current track duration to cumulative time for next track
                                        cumulative_time_ms += duration_ms
                                    
                                    # Add playlist summary
                                    total_duration_ms = sum(track.get('duration_ms', 0) for track in tracks)
                                    total_minutes = total_duration_ms // 60000
                                    total_hours = total_minutes // 60
                                    remaining_minutes = total_minutes % 60
                                    
                                    if total_hours > 0:
                                        duration_summary = f"{total_hours}h {remaining_minutes}m"
                                    else:
                                        duration_summary = f"{total_minutes}m"
                                    
                                    tracks_table += f"\n**Total duration:** {duration_summary}\n"
                                    
                                    # Add to chat
                                    st.session_state.messages.append({
                                        "role": "user", 
                                        "content": tracks_table
                                    })
                                    
                                    # Save conversation with playlist snapshot
                                    playlist_snapshot = get_playlist_snapshot(playlist, tracks)
                                    save_conversation(user_id, playlist_id, st.session_state.messages, playlist_snapshot)
                                    
                                    print(f"DEBUG: Added updated playlist content to conversation")
                                else:
                                    print(f"DEBUG: Playlist {playlist_name} unchanged, skipping content dump")
                                
                                # Set flag to auto-scroll to bottom
                                st.session_state.auto_scroll = True
                            else:
                                # Fallback if tracks couldn't be loaded
                                playlist_info = f"Playlist: {playlist_name} ({track_count} tracks) - Could not load track details"
                                st.session_state.messages.append({
                                    "role": "user", 
                                    "content": playlist_info
                                })
                                # Set flag to auto-scroll to bottom
                                st.session_state.auto_scroll = True
                    
                # Add visual separator between creator sections
                st.sidebar.markdown("")
            
            # Show search results summary
            if search_term:
                if filtered_playlists:
                    st.sidebar.write(f"**{len(filtered_playlists)}** playlists match '{search_term}' (by name or creator)")
                else:
                    st.sidebar.write("No playlists or creators match your search.")
                
            if search_term and not filtered_playlists:
                st.sidebar.write("No playlists or creators match your search.")
        else:
            st.sidebar.write("No playlists found.")
            st.sidebar.write("Create your first playlist to get started!")
    except Exception as e:
        st.sidebar.error(f"Error loading playlists: {str(e)}")

st.sidebar.markdown("---")

# Show current playlist if active
#if st.session_state.current_playlist_name:
#    st.info(f"🎵 Currently chatting about: **{st.session_state.current_playlist_name}**")

# Show login prompt if not connected to Spotify
if st.session_state.token_info is None:
    st.info("🎵 Connect to Spotify to create personalized playlists based on your music taste!")

# Display chat messages from history on app rerun (excluding system messages)
for message in st.session_state.messages:
    # Skip system messages in the display
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Auto-scroll to bottom if flag is set
if st.session_state.get("auto_scroll", False):
    st.session_state.auto_scroll = False  # Reset flag
    # Use JavaScript to scroll to bottom
    st.components.v1.html(
        """
        <script>
        setTimeout(function() {
            window.parent.document.querySelector('section.main').scrollTo({
                top: window.parent.document.querySelector('section.main').scrollHeight,
                behavior: 'smooth'
            });
        }, 100);
        </script>
        """,
        height=0,
    )

# Accept user input
if prompt := st.chat_input("Ask me to create a playlist, or chat about music..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat UI
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare system message for intelligent playlist enrichment
    system_content = ("You are Jemya, a playlist enrichment specialist who excels at intelligently inserting new tracks into existing playlists. "
                     "Your expertise lies in analyzing track-to-track transitions, understanding musical flow, and placing new songs at optimal positions within the existing structure. "
                     "When enriching playlists, you insert tracks between, before, or after existing songs based on tempo, key, energy, and mood compatibility. "
                     "For contrasting adjacent tracks, you add transition songs that bridge musical gaps smoothly. "
                     "Always explain your insertion logic: why each track goes in its specific position, how it creates better transitions, and how it enhances overall flow. "
                     "Mark new additions as 'ADDED after track X' or 'ADDED before track Y' with reasoning for placement. "
                     "Present results as enhanced playlist with original track numbers preserved and clear insertion explanations.")
    
    if st.session_state.token_info:
        system_content += " The user is connected to Spotify, so you can suggest creating playlists and provide detailed analysis of their existing collections."
    else:
        system_content += " The user is not connected to Spotify yet, so encourage them to connect their account to unlock the full potential of playlist analysis and creation."
    
    system_message = {
        "role": "system", 
        "content": system_content
    }

    # Get assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Prepare messages for OpenAI API
        api_messages = [system_message] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        try:
            for response_chunk in client.chat.completions.create(
                model="gpt-4o", #"gpt-5",
                messages=api_messages,
                stream=True,
                timeout=30,  # Add timeout
            ):
                full_response += (response_chunk.choices[0].delta.content or "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        except Exception as e:
            error_message = f"Sorry, I encountered a connection error: {str(e)[:100]}... Please try again."
            message_placeholder.markdown(error_message)
            full_response = error_message
            print(f"ERROR: OpenAI API error: {e}")
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # Auto-save conversation if we have an active playlist and changes were made
    if (st.session_state.current_playlist_id and st.session_state.current_user_id and 
        has_conversation_changed(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)):
        save_conversation(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
        # Also save the session state
        save_user_session(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.current_playlist_name)
        print(f"DEBUG: Auto-saved conversation and session after assistant response")
    
    # Set flag to auto-scroll to bottom
    st.session_state.auto_scroll = True

# Footer with Apply Changes button
st.markdown("---")

# Show Apply Changes button only if there's an active playlist and user is logged in
if (st.session_state.current_playlist_id and 
    st.session_state.current_playlist_name and 
    st.session_state.token_info and 
    len(st.session_state.messages) > 0):
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🎵 Apply Changes to Playlist", 
                    type="primary", 
                    use_container_width=True,
                    help=f"Apply AI suggestions to '{st.session_state.current_playlist_name}' on Spotify"):
            
            # Get AI suggestions from the conversation
            ai_suggestions = []
            for message in st.session_state.messages:
                if message["role"] == "assistant":
                    ai_suggestions.append(message["content"])
            
            if ai_suggestions:
                with st.spinner("Applying changes to your Spotify playlist..."):
                    success, message = apply_playlist_changes(
                        st.session_state.current_playlist_id, 
                        ai_suggestions
                    )
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                else:
                    st.error(f"❌ {message}")
            else:
                st.warning("No AI suggestions found to apply to the playlist.")

else:
    st.markdown("**Jemya** - Your AI-powered Spotify playlist generator 🎵✨")