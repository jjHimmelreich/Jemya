"""
Jemya - AI Playlist Generator
Main Streamlit application file (refactored version)
"""

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import base64

# Import our custom modules
from conversation_manager import ConversationManager
from spotify_manager import SpotifyManager
from ai_manager import AIManager

# Initialize managers
conversation_manager = ConversationManager()
spotify_manager = SpotifyManager()
ai_manager = AIManager()


def switch_to_playlist_conversation(user_id, playlist_id, playlist_name):
    """Switch to a specific playlist conversation"""
    # Save current conversation if there's an active playlist and it has changed
    if 'current_playlist_id' in st.session_state and st.session_state.current_playlist_id:
        current_user_id = st.session_state.get('current_user_id')
        if current_user_id and conversation_manager.has_conversation_changed(current_user_id, st.session_state.current_playlist_id, st.session_state.messages):
            conversation_manager.save_conversation(current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
            print(f"DEBUG: Saved changed conversation for playlist {st.session_state.current_playlist_id}")
        elif current_user_id:
            print(f"DEBUG: No changes detected, skipping save for playlist {st.session_state.current_playlist_id}")
    
    # Load conversation for the new playlist
    messages = conversation_manager.load_conversation(user_id, playlist_id)
    
    # Update session state
    st.session_state.messages = messages
    st.session_state.current_playlist_id = playlist_id
    st.session_state.current_playlist_name = playlist_name
    st.session_state.current_user_id = user_id
    
    # Save the user's session state
    conversation_manager.save_user_session(user_id, playlist_id, playlist_name)
    
    # Add system and welcome messages if this is a new conversation
    if not messages:
        # Add system message for playlist enrichment specialist
        system_message = ai_manager.generate_system_message(has_spotify_connection=True)
        
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


def preview_playlist_changes(playlist_id, track_suggestions):
    """Preview what the final playlist will look like after applying changes"""
    print("DEBUG: Starting preview_playlist_changes")
    token_info = spotify_manager.refresh_spotify_token_if_needed()
    if not token_info or not isinstance(token_info, dict) or 'access_token' not in token_info:
        print("DEBUG: No valid token for preview")
        return False, "No valid Spotify authentication", {}
    
    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        print("DEBUG: Created Spotify client for preview")
        
        # Extract desired playlist from AI suggestions
        try:
            # Ensure track_suggestions is a list
            if isinstance(track_suggestions, str):
                track_suggestions_list = [track_suggestions]
            else:
                track_suggestions_list = track_suggestions
            
            desired_playlist = ai_manager.extract_tracks_from_ai_response(track_suggestions_list)
            print(f"DEBUG: Extracted {len(desired_playlist) if desired_playlist else 0} tracks from AI response")
        except Exception as e:
            print(f"DEBUG: Error extracting tracks: {e}")
            return False, str(e), {}
        
        if not desired_playlist:
            print("DEBUG: No valid playlist found in AI response")
            return False, "No valid playlist found in AI response", {}
        
        # Get current playlist info and tracks
        current_tracks = spotify_manager.get_playlist_tracks(playlist_id)
        playlist_info = sp.playlist(playlist_id, fields="name,owner,public")
        
        # Create preview tracks by searching for desired tracks
        final_tracks = []
        not_found_tracks = []
        
        for track in desired_playlist:
            track_name = track.get('track_name', '')
            artist_name = track.get('artist', '')
            
            if not track_name or not artist_name:
                continue
                
            # Use the centralized search function from SpotifyManager
            found_track = spotify_manager.search_track_with_flexible_matching(sp, track_name, artist_name)
            
            if found_track:
                final_tracks.append({
                    'name': found_track['name'],
                    'artists': ', '.join([artist['name'] for artist in found_track['artists']]),
                    'album': found_track['album']['name'],
                    'duration_ms': found_track['duration_ms'],
                    'spotify_url': found_track['external_urls'].get('spotify', ''),
                    'is_new': True
                })
            else:
                not_found_tracks.append(f"{track_name} - {artist_name}")
        
        # Calculate changes
        tracks_to_add = len(final_tracks)
        tracks_to_remove = len(current_tracks)
        
        preview_data = {
            'final_tracks': final_tracks,
            'playlist_info': playlist_info,
            'tracks_not_found': not_found_tracks,
            'original_suggestions': desired_playlist,  # Include original AI suggestions
            'summary': {
                'will_add': tracks_to_add,
                'will_remove': tracks_to_remove,
                'not_found': len(not_found_tracks)
            }
        }
        
        print(f"DEBUG: Preview generated - found {len(final_tracks)} tracks, {len(not_found_tracks)} not found")
        return True, "Preview generated successfully", preview_data
        
    except Exception as e:
        print(f"ERROR: Exception in preview_playlist_changes: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Error previewing changes: {str(e)}", {}


def apply_playlist_changes(playlist_id, track_suggestions):
    """Apply AI-suggested changes by aligning playlist to desired state"""
    token_info = spotify_manager.refresh_spotify_token_if_needed()
    if not token_info or not isinstance(token_info, dict) or 'access_token' not in token_info:
        return False, "No valid Spotify authentication"
    
    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_id = sp.current_user()['id']
        
        # Extract desired playlist from AI suggestions
        try:
            desired_playlist = ai_manager.extract_tracks_from_ai_response(track_suggestions)
        except Exception as e:
            return False, str(e)
        
        if not desired_playlist:
            return False, "No valid playlist found in AI response"
        
        # Align playlist to desired state
        print("DEBUG: Aligning playlist to desired state...")
        result = spotify_manager.align_playlist_to_desired_state(playlist_id, sp, desired_playlist)
        
        # Log the changes for audit purposes
        change_details = {
            'tracks_added': result['added_count'],
            'tracks_removed': result['removed_count'],
            'tracks_not_found': result['not_found_count'],
            'added_tracks': result['added_tracks'],
            'not_found_tracks': result['not_found_tracks']
        }
        conversation_manager.save_playlist_change_log(user_id, playlist_id, change_details)
        
        # Create success message
        message_parts = []
        if result['added_count'] > 0:
            if result['added_count'] == 1:
                message_parts.append("Added 1 track")
            else:
                message_parts.append(f"Added {result['added_count']} tracks")
        
        if result['removed_count'] > 0:
            if result['removed_count'] == 1:
                message_parts.append("Removed 1 track")
            else:
                message_parts.append(f"Removed {result['removed_count']} tracks")
        
        if message_parts:
            final_message = " • ".join(message_parts)
        else:
            final_message = "Playlist aligned"
        
        if result['not_found_count'] > 0:
            final_message += f" ({result['not_found_count']} tracks not found)"
        
        return True, final_message
            
    except Exception as e:
        print(f"Error applying playlist changes: {e}")
        return False, f"Error applying changes: {str(e)}"


# Streamlit App Configuration
st.set_page_config(page_title="Jemya - Playlist Generator", page_icon="🎵")

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
    sp_oauth = spotify_manager.get_spotify_oauth()
    try:
        # Use get_cached_token instead of get_access_token with as_dict=True
        token_info = sp_oauth.get_cached_token()
        if not token_info:
            token_info = sp_oauth.get_access_token(code)
            if isinstance(token_info, str):
                # If it's a string, convert to dict format expected by our code
                token_info = {'access_token': token_info}
        
        st.session_state.token_info = token_info
        st.success("Successfully logged in to Spotify!")
        # Clear the code parameter and rerun
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Error during Spotify login: {str(e)}")


# Spotify login/logout section
if st.session_state.token_info is None:
    sp_oauth = spotify_manager.get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    
    # Use a link_button for direct navigation to Spotify auth
    if st.sidebar.link_button("🔗 Login with Spotify", auth_url, type="primary"):
        pass  # The link_button handles the redirect automatically
else:
    # User is logged in
    user_info = st.session_state.user_info
    
    # Get user info if not available yet
    if not user_info:
        user_info = spotify_manager.get_user_info()
        if user_info:
            st.session_state.user_info = user_info
    
    # ALWAYS check and restore session state if needed (not just on first login)
    if user_info:
        user_id = user_info.get('id')
        if user_id:
            # Check if session state needs restoration (e.g., after rerun)
            if (not st.session_state.current_playlist_id and 
                not st.session_state.current_playlist_name and 
                not st.session_state.current_user_id):
                
                print("DEBUG: Session state appears reset, attempting restoration...")
                last_session = conversation_manager.load_user_session(user_id)
                if last_session and last_session.get('last_playlist_id'):
                    playlist_id = last_session.get('last_playlist_id')
                    playlist_name = last_session.get('last_playlist_name', 'Unknown Playlist')
                    
                    # Load the last conversation without showing the loading message
                    print(f"DEBUG: Restoring last session - playlist: {playlist_name}")
                    messages = conversation_manager.load_conversation(user_id, playlist_id)
                    st.session_state.messages = messages
                    st.session_state.current_playlist_id = playlist_id
                    st.session_state.current_playlist_name = playlist_name
                    st.session_state.current_user_id = user_id
                    print(f"DEBUG: Session state restored - playlist_id: {bool(playlist_id)}, messages: {len(messages)}")
    
    if user_info:
        st.sidebar.success(f"{user_info.get('display_name', 'User')}!")
        
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            # Save current session before logging out
            if st.session_state.current_user_id and st.session_state.current_playlist_id:
                conversation_manager.save_user_session(st.session_state.current_user_id, 
                                st.session_state.current_playlist_id, 
                                st.session_state.current_playlist_name)
                # Also save the current conversation
                if conversation_manager.has_conversation_changed(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages):
                    conversation_manager.save_conversation(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
            
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
        playlists = spotify_manager.get_user_playlists()
        
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
                                st.session_state.user_info = spotify_manager.get_user_info()
                            
                            user_id = st.session_state.user_info.get('id') if st.session_state.user_info else 'unknown'
                            
                            # Switch to this playlist's conversation
                            switch_to_playlist_conversation(user_id, playlist_id, playlist_name)
                            
                            # Show loading message
                            with st.sidebar:
                                with st.spinner(f"Loading tracks from '{playlist_name}'..."):
                                    tracks = spotify_manager.get_playlist_tracks(playlist_id)
                            
                            if tracks:
                                # Check if playlist content has changed before adding to conversation
                                if conversation_manager.has_playlist_changed(user_id, playlist_id, playlist, tracks):
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
                                        start_time_str = spotify_manager.format_time_human_readable(cumulative_time_ms)
                                        
                                        # Get current track duration and format it
                                        duration_ms = track.get('duration_ms', 0)
                                        duration_str = spotify_manager.format_time_human_readable(duration_ms)
                                        
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
                                    playlist_snapshot = conversation_manager.get_playlist_snapshot(playlist, tracks)
                                    conversation_manager.save_conversation(user_id, playlist_id, st.session_state.messages, playlist_snapshot)
                                    
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
    system_content = ai_manager.generate_system_message(has_spotify_connection=bool(st.session_state.token_info))
    system_message = {"role": "system", "content": system_content}

    # Get assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Prepare messages for OpenAI API
        api_messages = [system_message] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        try:
            for response_chunk in ai_manager.client.chat.completions.create(
                model="gpt-4o",
                messages=api_messages,
                stream=True,
                timeout=30,
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
        conversation_manager.has_conversation_changed(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)):
        conversation_manager.save_conversation(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
        # Also save the session state
        conversation_manager.save_user_session(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.current_playlist_name)
        print(f"DEBUG: Auto-saved conversation and session after assistant response")
    
    # Set flag to auto-scroll to bottom
    st.session_state.auto_scroll = True

# Footer with Apply Changes button
st.markdown("---")

# Initialize session state for preview and apply tracking (always initialize)
if 'show_preview' not in st.session_state:
    st.session_state.show_preview = False
if 'preview_data' not in st.session_state:
    st.session_state.preview_data = None
if 'last_apply_time' not in st.session_state:
    st.session_state.last_apply_time = 0
if 'applying_changes' not in st.session_state:
    st.session_state.applying_changes = False
if 'generating_preview' not in st.session_state:
    st.session_state.generating_preview = False

# Check if buttons should be enabled (but always show them)
print(f"DEBUG: Button visibility check - playlist_id: {bool(st.session_state.current_playlist_id)}, playlist_name: {bool(st.session_state.current_playlist_name)}, token: {bool(st.session_state.token_info)}, messages: {len(st.session_state.messages)}")
buttons_enabled = (st.session_state.current_playlist_id and 
                  st.session_state.current_playlist_name and 
                  st.session_state.token_info and 
                  len(st.session_state.messages) > 0)

if buttons_enabled:
    print("DEBUG: *** BUTTONS ENABLED ***")
else:
    print("DEBUG: *** BUTTONS DISABLED - conditions not met ***")

# Get AI suggestions from the conversation (use the latest assistant message)
ai_suggestions = None
if len(st.session_state.messages) > 0:
    for message in reversed(st.session_state.messages):  # Get the latest assistant message
        if message["role"] == "assistant":
            ai_suggestions = message["content"]
            break

print(f"DEBUG: Found {len(st.session_state.messages)} messages, ai_suggestions: {ai_suggestions is not None}")
if ai_suggestions:
    print(f"DEBUG: AI suggestions preview (first 200 chars): {ai_suggestions[:200]}...")

# Always show buttons, but with different states based on conditions
if not buttons_enabled:
    st.info("🎵 Select a playlist and start a conversation to see action buttons!")
    # Still show buttons but all disabled
    button_col1, button_col2, button_col3, button_col4, button_col5 = st.columns(5)
    buttons_disabled = True
elif not ai_suggestions:
    st.warning("No AI suggestions found to apply to the playlist.")
    # Still show buttons but all disabled
    button_col1, button_col2, button_col3, button_col4, button_col5 = st.columns(5)
    buttons_disabled = True
else:
    # Show all 5 conversation control buttons horizontally (fully functional)
    # Horizontal layout for all 5 conversation control buttons
    button_col1, button_col2, button_col3, button_col4, button_col5 = st.columns(5)
    buttons_disabled = False

with button_col1:
                    # Open in Spotify button with icon
                    spotify_url = f"https://open.spotify.com/playlist/{st.session_state.current_playlist_id}"
                    spotify_icon_b64 = st.session_state.get("spotify_icon_b64", "")
                    if spotify_icon_b64:
                        st.markdown(f"""
                            <div style="text-align: center;">
                                <a href="{spotify_url}" target="_blank" style="
                                    display: inline-block;
                                    padding: 0.5rem;
                                    background-color: #1DB954;
                                    color: white;
                                    text-decoration: none;
                                    border-radius: 0.5rem;
                                    width: 100%;
                                    text-align: center;
                                    box-sizing: border-box;
                                    transition: all 0.2s;
                                " onmouseover="this.style.backgroundColor='#1ed760'" 
                                   onmouseout="this.style.backgroundColor='#1DB954'"
                                   title="Open in Spotify">
                                    <img src="data:image/png;base64,{spotify_icon_b64}" style="height: 20px; vertical-align: middle;">
                                </a>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Fallback to text if icon not loaded
                        st.markdown(f"""
                            <div style="text-align: center;">
                                <a href="{spotify_url}" target="_blank" style="
                                    display: inline-block;
                                    padding: 0.5rem;
                                    background-color: #1DB954;
                                    color: white;
                                    text-decoration: none;
                                    border-radius: 0.5rem;
                                    width: 100%;
                                    text-align: center;
                                    box-sizing: border-box;
                                    font-size: 14px;
                                    transition: all 0.2s;
                                " onmouseover="this.style.backgroundColor='#1ed760'" 
                                   onmouseout="this.style.backgroundColor='#1DB954'"
                                   title="Open in Spotify">
                                    🎧 Spotify
                                </a>
                            </div>
                        """, unsafe_allow_html=True)
            
with button_col2:
                    print(f"DEBUG: Button state check - generating_preview: {st.session_state.get('generating_preview', False)}, applying_changes: {st.session_state.get('applying_changes', False)}")
                    is_disabled = st.session_state.generating_preview or st.session_state.applying_changes
                    print(f"DEBUG: Button disabled state: {is_disabled}")
                    print(f"DEBUG: Current playlist name: '{st.session_state.current_playlist_name}'")
                    
                    if st.session_state.generating_preview:
                        print("DEBUG: Showing generating preview message")
                        st.info("⏳ Generating preview...")
                    # Always show the Preview button, but disable it based on state
                    print("DEBUG: Rendering Preview button (always visible)")
                    if st.session_state.generating_preview:
                        button_text = "⏳ Generating..."
                        help_text = "Preview is being generated..."
                        is_disabled = True
                    else:
                        button_text = "👀 Preview"
                        help_text = f"Preview what will be added to '{st.session_state.current_playlist_name}'"
                        is_disabled = st.session_state.applying_changes
                    
                    preview_clicked = st.button(
                        button_text,
                        key="preview_btn_always",
                        type="secondary",
                        disabled=is_disabled,
                        use_container_width=True,
                        help=help_text
                    )
                    print(f"DEBUG: Preview button clicked: {preview_clicked}")
                    
                    if preview_clicked:
                        print("DEBUG: *** PREVIEW BUTTON CLICKED! ***")
                        print(f"DEBUG: Before rerun - playlist_id: {st.session_state.current_playlist_id}")
                        print(f"DEBUG: Before rerun - playlist_name: {st.session_state.current_playlist_name}")
                        print(f"DEBUG: Before rerun - token exists: {st.session_state.token_info is not None}")
                        st.session_state.generating_preview = True
                        print("DEBUG: Set generating_preview = True, calling rerun")
                        st.rerun()
            
# Handle preview generation after button click
if st.session_state.generating_preview:
                    print("DEBUG: generating_preview is True, showing spinner and calling preview function")
                    with st.spinner("Analyzing suggested changes..."):
                        success, message, preview_data = preview_playlist_changes(
                            st.session_state.current_playlist_id, 
                            ai_suggestions
                        )
                    
                    print(f"DEBUG: Preview function returned: success={success}, message='{message}', preview_data keys: {list(preview_data.keys()) if isinstance(preview_data, dict) else 'Not a dict'}")
                    st.session_state.generating_preview = False
                    
                    if success:
                        print("DEBUG: Preview successful, setting show_preview = True")
                        st.session_state.show_preview = True
                        st.session_state.preview_data = preview_data
                        st.rerun()
                    else:
                        print(f"DEBUG: Preview failed: {message}")
                        st.error(f"❌ {message}")
                        st.rerun()
            
with button_col3:
                    # Quick apply button (for users who don't want preview)
                    current_time = time.time()
                    time_since_last_apply = current_time - st.session_state.last_apply_time
                    can_apply = time_since_last_apply > 10  # 10 second cooldown
                    
                    # Quick Apply button - always visible but disabled when not ready
                    is_disabled = (st.session_state.applying_changes or 
                                 st.session_state.generating_preview or 
                                 not can_apply)
                    
                    # Determine help text based on state
                    if st.session_state.applying_changes:
                        help_text = "⏳ Currently applying changes..."
                    elif st.session_state.generating_preview:
                        help_text = "⏳ Generating preview..."
                    elif not can_apply:
                        remaining_time = int(10 - time_since_last_apply)
                        help_text = f"⏰ Please wait {remaining_time} seconds before applying again"
                    else:
                        help_text = f"Directly apply AI suggestions to '{st.session_state.current_playlist_name}' without preview"
                    
                    if st.button("⚡ Quick Apply (No Preview)", 
                                type="primary", 
                                use_container_width=True,
                                help=help_text,
                                disabled=is_disabled):
                            
                            st.session_state.applying_changes = True
                            st.session_state.last_apply_time = current_time
                            
                            with st.spinner("Applying changes to your Spotify playlist..."):
                                success, message = apply_playlist_changes(
                                    st.session_state.current_playlist_id, 
                                    ai_suggestions
                                )
                            
                            st.session_state.applying_changes = False
                            
                            if success:
                                st.success(f"✅ {message}")
                                st.info("🎵 Your playlist has been updated! Use the 'Open in Spotify' button above to listen.")
                                # Force rerun to refresh UI and show "Open in Spotify" button
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
            
with button_col4:
                    # Reset Conversation button - always visible but disabled when no messages
                    is_disabled = (st.session_state.applying_changes or 
                                 st.session_state.generating_preview or 
                                 len(st.session_state.messages) <= 1)  # Disable if no conversation to reset
                    
                    if st.button("🔄 Reset", 
                                type="secondary",
                                use_container_width=True,
                                help=f"Clear conversation history for '{st.session_state.current_playlist_name}' and start fresh" if not is_disabled else "No conversation to reset",
                                disabled=is_disabled):
                        
                        if len(st.session_state.messages) > 1:  # Double-check before reset
                            
                            # Delete the conversation file
                            success = conversation_manager.delete_conversation(
                                st.session_state.current_user_id, 
                                st.session_state.current_playlist_id
                            )
                            
                            if success:
                                st.success("Conversation reset!")
                            else:
                                st.info("No conversation history to reset")
                            
                            # Clear current messages in session
                            st.session_state.messages = []
                            
                            # Clear any preview state
                            st.session_state.show_preview = False
                            st.session_state.preview_data = None
                            st.session_state.applying_changes = False
                            st.session_state.generating_preview = False
                            
                            # Clear playlist cache to force reload
                            if 'cached_playlists' in st.session_state:
                                del st.session_state.cached_playlists
                            if 'playlists_cache_time' in st.session_state:
                                del st.session_state.playlists_cache_time
                            
                            # Force rerun to refresh everything
                            st.rerun()
            
with button_col5:
                    # Cancel/Clear button - always visible but disabled when no messages
                    is_disabled = (st.session_state.applying_changes or 
                                 st.session_state.generating_preview or 
                                 len(st.session_state.messages) <= 1)  # Disable if no messages to clear
                    
                    if st.button("❌ Clear", 
                                type="secondary",
                                use_container_width=True,
                                help="Clear current AI suggestions and start over" if not is_disabled else "No suggestions to clear",
                                disabled=is_disabled):
                        
                        if len(st.session_state.messages) > 1:  # Double-check before clearing
                            
                            # Clear any AI suggestions by removing the last AI response
                            if st.session_state.messages and st.session_state.messages[-1].get('role') == 'assistant':
                                st.session_state.messages.pop()
                            
                            # Clear any preview state
                            st.session_state.show_preview = False
                            st.session_state.preview_data = None
                            
                            # Force rerun to refresh
                            st.rerun()

            # Show preview if available
print(f"DEBUG: Checking preview display - show_preview: {st.session_state.get('show_preview', False)}, preview_data exists: {st.session_state.get('preview_data') is not None}")
if st.session_state.show_preview and st.session_state.preview_data:
                preview = st.session_state.preview_data
                summary = preview['summary']
                print(f"DEBUG: Displaying preview with {len(preview.get('final_tracks', []))} final tracks")
                
                st.markdown("### 📋 Preview: Final Playlist")
                
                # Show AI-recommended tracks table (both found and not found)
                if 'final_tracks' in preview and 'playlist_info' in preview:
                    final_tracks = preview['final_tracks']
                    not_found_tracks = preview.get('tracks_not_found', [])
                    playlist_info = preview['playlist_info']
                    
                    # Extract playlist owner information
                    owner_data = playlist_info.get('owner', {})
                    if isinstance(owner_data, dict):
                        owner_name = owner_data.get('display_name', 'Unknown')
                        owner_id = owner_data.get('id', '')
                    else:
                        owner_name = 'Unknown'
                        owner_id = ''
                    
                    # Check if it's a public playlist
                    is_public = playlist_info.get('public', False)
                    
                    # Calculate total AI recommendations
                    total_ai_tracks = len(final_tracks) + len(not_found_tracks)
                    
                    # Create formatted table of AI recommendations
                    tracks_table = f"## 🎵 {playlist_info.get('name', 'Playlist')} (Preview)\n\n"
                    tracks_table += f"**Created by:** {owner_name}"
                    # Only show user ID if no display name exists
                    if not owner_name or owner_name == 'Unknown':
                        if owner_id:
                            tracks_table += f" (@{owner_id})"
                    tracks_table += f" • **{total_ai_tracks} AI recommendations** ({len(final_tracks)} found, {len(not_found_tracks)} not found) • {'Public' if is_public else 'Private'}\n\n"
                    tracks_table += "| # | Track | Artist | Album | Duration | Start Time | Status |\n"
                    tracks_table += "|---|-------|--------|-------|----------|------------|--------|\n"
                    
                    # First, create a map of found tracks by their original names
                    found_tracks_map = {}
                    for track in final_tracks:
                        # Try to match with original AI suggestions by name similarity
                        found_tracks_map[track['name'].lower()] = track
                    
                    # Get the original AI suggestions to maintain order
                    original_suggestions = preview.get('original_suggestions', [])
                    
                    cumulative_time_ms = 0
                    track_counter = 1
                    
                    # Show tracks in AI-recommended order
                    if original_suggestions:
                        for suggestion in original_suggestions:
                            track_name = suggestion.get('track_name', 'Unknown')
                            artist_name = suggestion.get('artist', 'Unknown')
                            
                            # Try to find matching track in found tracks
                            found_track = None
                            for track in final_tracks:
                                if (track_name.lower() in track['name'].lower() or 
                                    track['name'].lower() in track_name.lower()):
                                    found_track = track
                                    break
                            
                            if found_track:
                                # Format start time
                                start_time_str = spotify_manager.format_time_human_readable(cumulative_time_ms)
                                
                                # Get current track duration and format it
                                duration_ms = found_track.get('duration_ms', 0)
                                duration_str = spotify_manager.format_time_human_readable(duration_ms)
                                
                                # Truncate long names for table readability
                                full_track_name = found_track.get('name', 'Unknown')
                                display_track_name = full_track_name[:40]
                                if len(full_track_name) > 40:
                                    display_track_name += "..."
                                
                                # Create clickable link if Spotify URL exists
                                spotify_url = found_track.get('spotify_url', '')
                                if spotify_url:
                                    track_name_display = f"[{display_track_name}]({spotify_url})"
                                else:
                                    track_name_display = display_track_name
                                
                                display_artist_name = found_track.get('artists', 'Unknown')[:30]
                                if len(found_track.get('artists', '')) > 30:
                                    display_artist_name += "..."
                                
                                album_name = found_track.get('album', 'Unknown')[:30]
                                if len(found_track.get('album', '')) > 30:
                                    album_name += "..."
                                
                                status = "✅ Found"
                                
                                tracks_table += f"| {track_counter} | {track_name_display} | {display_artist_name} | {album_name} | {duration_str} | {start_time_str} | {status} |\n"
                                
                                # Add current track duration to cumulative time
                                cumulative_time_ms += duration_ms
                            else:
                                # Track not found - show AI suggestion without link
                                display_track_name = track_name[:40]
                                if len(track_name) > 40:
                                    display_track_name += "..."
                                
                                display_artist_name = artist_name[:30]
                                if len(artist_name) > 30:
                                    display_artist_name += "..."
                                
                                status = "❌ Not Found"
                                
                                tracks_table += f"| {track_counter} | {display_track_name} | {display_artist_name} | - | - | - | {status} |\n"
                            
                            track_counter += 1
                    else:
                        # Fallback: show found tracks first, then not found
                        for track in final_tracks:
                            # Format start time
                            start_time_str = spotify_manager.format_time_human_readable(cumulative_time_ms)
                            
                            # Get current track duration and format it
                            duration_ms = track.get('duration_ms', 0)
                            duration_str = spotify_manager.format_time_human_readable(duration_ms)
                            
                            # Truncate long names for table readability
                            full_track_name = track.get('name', 'Unknown')
                            display_track_name = full_track_name[:40]
                            if len(full_track_name) > 40:
                                display_track_name += "..."
                            
                            # Create clickable link if Spotify URL exists
                            spotify_url = track.get('spotify_url', '')
                            if spotify_url:
                                track_name_display = f"[{display_track_name}]({spotify_url})"
                            else:
                                track_name_display = display_track_name
                            
                            display_artist_name = track.get('artists', 'Unknown')[:30]
                            if len(track.get('artists', '')) > 30:
                                display_artist_name += "..."
                            
                            album_name = track.get('album', 'Unknown')[:30]
                            if len(track.get('album', '')) > 30:
                                album_name += "..."
                            
                            status = "✅ Found"
                            
                            tracks_table += f"| {track_counter} | {track_name_display} | {display_artist_name} | {album_name} | {duration_str} | {start_time_str} | {status} |\n"
                            
                            # Add current track duration to cumulative time
                            cumulative_time_ms += duration_ms
                            track_counter += 1
                        
                        # Show not found tracks
                        for not_found in not_found_tracks:
                            if ' - ' in not_found:
                                track_name, artist_name = not_found.split(' - ', 1)
                            else:
                                track_name = not_found
                                artist_name = "Unknown"
                            
                            display_track_name = track_name[:40]
                            if len(track_name) > 40:
                                display_track_name += "..."
                            
                            display_artist_name = artist_name[:30]
                            if len(artist_name) > 30:
                                display_artist_name += "..."
                            
                            status = "❌ Not Found"
                            
                            tracks_table += f"| {track_counter} | {display_track_name} | {display_artist_name} | - | - | - | {status} |\n"
                            track_counter += 1
                    
                    # Add playlist summary
                    total_duration_ms = sum(track.get('duration_ms', 0) for track in final_tracks)
                    total_minutes = total_duration_ms // 60000
                    total_hours = total_minutes // 60
                    remaining_minutes = total_minutes % 60
                    
                    if total_hours > 0:
                        duration_summary = f"{total_hours}h {remaining_minutes}m"
                    else:
                        duration_summary = f"{total_minutes}m"
                    
                    tracks_table += f"\n**Total duration:** {duration_summary}"
                    
                    # Add summary of changes
                    change_notes = []
                    if summary['will_add'] > 0:
                        change_notes.append(f"**{summary['will_add']} tracks** will be in final playlist")
                    if summary['will_remove'] > 0:
                        change_notes.append(f"**{summary['will_remove']} current tracks** will be replaced")
                    if summary['not_found'] > 0:
                        change_notes.append(f"**{summary['not_found']} tracks** not found")
                    
                    if change_notes:
                        tracks_table += " • " + " • ".join(change_notes)
                    
                    tracks_table += "\n\n*This shows the complete final playlist after AI changes*"
                    
                    st.markdown(tracks_table)
                    
                    if len(preview['tracks_not_found']) > 10:
                        st.markdown(f"*... and {len(preview['tracks_not_found']) - 10} more not found*")
                
                st.markdown("---")
                
                # Apply and Cancel buttons - keep consistent with main button layout
                col_w, col_x, col_y, col_z, col_v = st.columns(5)
                
                with col_w:
                    # Open in Spotify button with icon (consistent with main layout)
                    spotify_url = f"https://open.spotify.com/playlist/{st.session_state.current_playlist_id}"
                    spotify_icon_b64 = st.session_state.get("spotify_icon_b64", "")
                    if spotify_icon_b64:
                        st.markdown(f"""
                            <div style="text-align: center;">
                                <a href="{spotify_url}" target="_blank" style="
                                    display: inline-block;
                                    padding: 0.5rem;
                                    background-color: #1DB954;
                                    color: white;
                                    text-decoration: none;
                                    border-radius: 0.5rem;
                                    width: 100%;
                                    text-align: center;
                                    box-sizing: border-box;
                                    transition: all 0.2s;
                                " onmouseover="this.style.backgroundColor='#1ed760'" 
                                   onmouseout="this.style.backgroundColor='#1DB954'"
                                   title="Open in Spotify">
                                    <img src="data:image/png;base64,{spotify_icon_b64}" style="height: 20px; vertical-align: middle;">
                                </a>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Fallback to text if icon not loaded
                        st.markdown(f"""
                            <div style="text-align: center;">
                                <a href="{spotify_url}" target="_blank" style="
                                    display: inline-block;
                                    padding: 0.5rem;
                                    background-color: #1DB954;
                                    color: white;
                                    text-decoration: none;
                                    border-radius: 0.5rem;
                                    width: 100%;
                                    text-align: center;
                                    box-sizing: border-box;
                                    font-size: 14px;
                                    transition: all 0.2s;
                                " onmouseover="this.style.backgroundColor='#1ed760'" 
                                   onmouseout="this.style.backgroundColor='#1DB954'"
                                   title="Open in Spotify">
                                    🎧 Spotify
                                </a>
                            </div>
                        """, unsafe_allow_html=True)
                
                with col_z:  # Changed from col_y to col_z
                    # Check if enough time has passed since last apply (prevent rapid clicking)
                    current_time = time.time()
                    time_since_last_apply = current_time - st.session_state.last_apply_time
                    can_apply = time_since_last_apply > 10  # 10 second cooldown
                    
                    # Apply Changes button - always visible but disabled when not ready
                    is_disabled = (st.session_state.applying_changes or 
                                 st.session_state.generating_preview or 
                                 not can_apply)
                    
                    # Determine help text based on state
                    if st.session_state.applying_changes:
                        help_text = "⏳ Currently applying changes..."
                    elif st.session_state.generating_preview:
                        help_text = "⏳ Generating preview..."
                    elif not can_apply:
                        remaining_time = int(10 - time_since_last_apply)
                        help_text = f"⏰ Please wait {remaining_time} seconds before applying again"
                    else:
                        help_text = "Apply the changes shown above to your Spotify playlist"
                    
                    if st.button("🎵 Apply Changes", 
                                type="primary", 
                                use_container_width=True,
                                help=help_text,
                                disabled=is_disabled):
                        
                        if summary['will_add'] > 0:
                            st.session_state.applying_changes = True
                            st.session_state.last_apply_time = current_time
                            
                            with st.spinner("Applying changes to your Spotify playlist..."):
                                success, message = apply_playlist_changes(
                                    st.session_state.current_playlist_id, 
                                    ai_suggestions
                                )
                            
                            st.session_state.applying_changes = False
                            
                            if success:
                                st.success(f"✅ {message}")     
                                st.info("🎵 Your playlist has been updated! Use the 'Open in Spotify' button above to listen.")                           
                                # Clear preview
                                st.session_state.show_preview = False
                                st.session_state.preview_data = None
                                # Force rerun to refresh UI and show "Open in Spotify" button
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                        else:
                            st.warning("No new tracks to add to the playlist.")
                
                with col_v:  # Changed from col_y to col_v
                    if st.button("❌ Cancel", 
                                type="secondary", 
                                use_container_width=True,
                                help="Cancel and don't apply any changes"):
                        st.session_state.show_preview = False
                        st.session_state.preview_data = None
                        st.rerun()

# Footer
st.markdown("**Jemya** - Your AI-powered Spotify playlist generator 🎵✨")