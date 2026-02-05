"""
Jemya - AI Playlist Generator
Main Streamlit application file (refactored version)
"""

import base64
import time

import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth

from ai_manager import AIManager
from mcp_manager import MCPManager
# Import our custom modules
from conversation_manager import ConversationManager
from spotify_manager import SpotifyManager

# Initialize managers
conversation_manager = ConversationManager()
spotify_manager = SpotifyManager()
ai_manager = AIManager()  # Will be re-initialized with MCP if needed


def switch_to_playlist_conversation(user_id, playlist_id, playlist_name):
    """Switch to a specific playlist conversation"""
    print(f"DEBUG: Switching to conversation for playlist '{playlist_name}' ({playlist_id})")

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
        # Store results with original track info for proper correlation
        track_results = []
        not_found_tracks = []
        
        for track in desired_playlist:
            track_name = track.get('track_name', '')
            artist_name = track.get('artist', '')
            
            if not track_name or not artist_name:
                continue
                
            # Use the centralized search function from SpotifyManager
            found_track = spotify_manager.search_track_with_flexible_matching(sp, track_name, artist_name)
            
            if found_track:
                track_results.append({
                    'original_track_name': track_name,
                    'original_artist': artist_name,
                    'found_track': {
                        'name': found_track['name'],
                        'artists': ', '.join([artist['name'] for artist in found_track['artists']]),
                        'album': found_track['album']['name'],
                        'duration_ms': found_track['duration_ms'],
                        'spotify_url': found_track['external_urls'].get('spotify', ''),
                        'is_new': True
                    },
                    'status': 'found'
                })
            else:
                track_results.append({
                    'original_track_name': track_name,
                    'original_artist': artist_name,
                    'found_track': None,
                    'status': 'not_found'
                })
                not_found_tracks.append(f"{track_name} - {artist_name}")
        
        # Extract just the found tracks for backward compatibility
        final_tracks = [result['found_track'] for result in track_results if result['status'] == 'found']
        
        # Calculate changes
        tracks_to_add = len(final_tracks)
        tracks_to_remove = len(current_tracks)
        
        preview_data = {
            'final_tracks': final_tracks,
            'playlist_info': playlist_info,
            'tracks_not_found': not_found_tracks,
            'original_suggestions': desired_playlist,  # Include original AI suggestions
            'track_results': track_results,  # Include detailed results with correlations
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

# Add CSS to remove link underlines, improve button alignment, and create fixed control panel
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
    
    /* Add bottom padding to main content to prevent overlap */
    .main .block-container {
        padding-bottom: 160px !important;
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

# Restore Spotify token from cache if available (for browser refresh persistence)
if st.session_state.token_info is None:
    sp_oauth = spotify_manager.get_spotify_oauth()
    cached_token = sp_oauth.get_cached_token()
    if cached_token:
        print("DEBUG: Restored token from cache file after page refresh")
        st.session_state.token_info = cached_token

# Sidebar for Spotify functionality
st.sidebar.title("Jemya - AI Playlist Generator")

# MCP Mode toggle (experimental feature)
st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ Advanced Settings", expanded=False):
    mcp_mode = st.checkbox(
        "🔬 Enable MCP Mode (Experimental)",
        value=st.session_state.get('mcp_mode', False),
        help="Enable Model Context Protocol for cross-playlist operations. Allows AI to read and combine multiple playlists."
    )
    st.session_state.mcp_mode = mcp_mode
    
    if mcp_mode:
        st.info(
            "🎯 **MCP Mode Enabled**\n\n"
            "AI can now:\n"
            "• Read multiple playlists\n"
            "• Combine playlists\n"
            "• Merge & deduplicate\n"
            "• Split playlists\n\n"
            "Try: *'Combine my workout playlists'*"
        )

st.sidebar.markdown("---")


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
    
    # Create a clickable link that opens in the same window
    st.sidebar.markdown(
        f"""
        <a href="{auth_url}" target="_self" style="
            display: inline-block; 
            background-color: #1DB954; 
            color: white; 
            padding: 0.5rem 1rem; 
            text-decoration: none; 
            border-radius: 0.5rem; 
            font-weight: bold;
            text-align: center;
            margin: 0.5rem 0;
        ">🔗 Login with Spotify</a>
        """,
        unsafe_allow_html=True
    )
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
        # Compact user info display
        col_user, col_logout = st.sidebar.columns([2, 1])
        with col_user:
            st.markdown(f"👤 **{user_info.get('display_name', 'User')}**")
        with col_logout:
            if st.button("Logout", key="logout_button", use_container_width=True):
                # Save current session before logging out
                if st.session_state.current_user_id and st.session_state.current_playlist_id:
                    conversation_manager.save_user_session(st.session_state.current_user_id, 
                                    st.session_state.current_playlist_id, 
                                    st.session_state.current_playlist_name)
                    # Also save the current conversation
                    if conversation_manager.has_conversation_changed(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages):
                        conversation_manager.save_conversation(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
                
                # Clear the cached token file
                import os
                cache_file = ".spotify_token_cache"
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    print("DEBUG: Removed token cache file on logout")
                
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
    
    # Full-width Create New Playlist button
    if st.sidebar.button("➕ Create New Playlist", help="Create a new playlist", key="create_playlist_button", type="primary", use_container_width=True):
        st.session_state.show_create_dialog = True
        st.rerun()
    
    # Add controls on the same line - checkbox and reload button
    col1, col2 = st.sidebar.columns([3, 2])
    
    with col1:
        # Checkbox to filter playlists
        show_only_mine = st.checkbox("Created by me", key="filter_my_playlists", value=True, help="Show only playlists created by you")
    
    with col2:
        # Add reload playlists button for debugging
        if st.button("🔄 Reload", help="Clear cache and refresh playlist data", key="reload_playlists"):
            print(f"DEBUG: Reload button clicked - token_info exists: {st.session_state.token_info is not None}")
            # Clear the playlist cache to force refresh
            if 'cached_playlists' in st.session_state:
                del st.session_state.cached_playlists
            if 'playlists_cache_time' in st.session_state:
                del st.session_state.playlists_cache_time
            print(f"DEBUG: Cache cleared, about to rerun - token_info still exists: {st.session_state.token_info is not None}")
            st.rerun()
    
    # Create playlist dialog
    if st.session_state.get('show_create_dialog', False):
        with st.sidebar.form(key='create_playlist_form', clear_on_submit=True):
            st.markdown("### Create New Playlist")
            new_playlist_name = st.text_input("Playlist name:", placeholder="My Awesome Playlist", key="new_playlist_name_input")
            new_playlist_description = st.text_area("Description (optional):", placeholder="A great collection of songs...", key="new_playlist_desc_input")
            is_public = st.checkbox("Make public", value=False, key="new_playlist_public")
            
            col_submit, col_cancel = st.columns(2)
            with col_submit:
                submit_button = st.form_submit_button("✅ Create", type="primary", use_container_width=True)
            with col_cancel:
                cancel_button = st.form_submit_button("❌ Cancel", use_container_width=True)
            
            if submit_button and new_playlist_name:
                # Create the playlist
                success, message, new_playlist_id = spotify_manager.create_playlist(
                    new_playlist_name, 
                    description=new_playlist_description,
                    public=is_public
                )
                
                if success:
                    st.sidebar.success(f"✅ {message}")
                    # Clear cache to refresh playlist list
                    if 'cached_playlists' in st.session_state:
                        del st.session_state.cached_playlists
                    if 'playlists_cache_time' in st.session_state:
                        del st.session_state.playlists_cache_time
                    st.session_state.show_create_dialog = False
                    
                    # Switch to the new playlist conversation
                    if new_playlist_id:
                        user_id = st.session_state.user_info.get('id') if st.session_state.user_info else None
                        if user_id:
                            switch_to_playlist_conversation(user_id, new_playlist_id, new_playlist_name)
                    
                    st.rerun()
                else:
                    st.sidebar.error(f"❌ {message}")
            elif submit_button:
                st.sidebar.warning("Please enter a playlist name")
            
            if cancel_button:
                st.session_state.show_create_dialog = False
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
                            elif tracks is not None and len(tracks) == 0:
                                # Empty playlist (newly created) - show friendly message
                                # Extract playlist owner information
                                owner_data = playlist.get('owner', {})
                                if isinstance(owner_data, dict):
                                    owner_name = owner_data.get('display_name', 'Unknown')
                                else:
                                    owner_name = 'Unknown'
                                
                                is_public = playlist.get('public', False)
                                
                                empty_playlist_msg = f"## 🎵 {playlist_name}\n\n"
                                empty_playlist_msg += f"**Created by:** {owner_name} • **0 tracks** • {'Public' if is_public else 'Private'}\n\n"
                                empty_playlist_msg += "*This playlist is empty. Start adding tracks by telling me what kind of music you'd like!*"
                                
                                st.session_state.messages.append({
                                    "role": "user", 
                                    "content": empty_playlist_msg
                                })
                                
                                # Save conversation
                                playlist_snapshot = conversation_manager.get_playlist_snapshot(playlist, [])
                                conversation_manager.save_conversation(user_id, playlist_id, st.session_state.messages, playlist_snapshot)
                                
                                # Set flag to auto-scroll to bottom
                                st.session_state.auto_scroll = True
                            else:
                                # Actual error loading tracks
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

# Display chat messages from history on app rerun (excluding system messages) - only when logged in
if st.session_state.token_info is not None:
    for message in st.session_state.messages:
        # Skip system messages in the display
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

# Auto-scroll to bottom if flag is set - only when logged in
if st.session_state.token_info is not None and st.session_state.get("auto_scroll", False):
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

# Chat input processing - only when logged in
if st.session_state.token_info is not None:
    
    # Handle user input if provided (this will be processed before the UI is rendered)
    if 'pending_prompt' in st.session_state and st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        del st.session_state.pending_prompt
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat UI
        with st.chat_message("user"):
            st.markdown(prompt)

        # Check if MCP mode is enabled
        mcp_mode_enabled = st.session_state.get('mcp_mode', False)
        
        if mcp_mode_enabled:
            # MCP Mode: Use function calling for cross-playlist operations
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                try:
                    # Initialize MCP manager
                    token_info = st.session_state.token_info
                    access_token = token_info.get('access_token') if isinstance(token_info, dict) else None
                    
                    message_placeholder.markdown("🔬 **MCP Mode Active** - Initializing...\n\n")
                    
                    # Create async wrapper to handle all MCP operations in one event loop
                    import asyncio
                    
                    async def run_mcp_mode():
                        # Create MCP manager and connect
                        mcp_manager = MCPManager(access_token=access_token)
                        await mcp_manager.connect()
                        
                        try:
                            # Create AI manager with MCP support
                            ai_manager_mcp = AIManager(mcp_manager=mcp_manager)
                            
                            # Prepare system message for MCP mode
                            system_content = ai_manager_mcp.generate_system_message(
                                has_spotify_connection=True,
                                mcp_mode=True
                            )
                            
                            # Prepare conversation history (exclude current user message)
                            conversation_history = [{"role": "system", "content": system_content}]
                            for msg in st.session_state.messages[:-1]:  # Exclude last user message
                                if msg["role"] != "system":
                                    conversation_history.append({"role": msg["role"], "content": msg["content"]})
                            
                            # Call AI with MCP tools
                            result = await ai_manager_mcp.generate_with_mcp(
                                user_message=prompt,
                                conversation_history=conversation_history
                            )
                            
                            return result
                            
                        finally:
                            # Always disconnect
                            await mcp_manager.disconnect()
                    
                    message_placeholder.markdown("🔬 **MCP Mode Active** - Calling AI...\n\n")
                    
                    # Run the async function in a new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        result = loop.run_until_complete(run_mcp_mode())
                    finally:
                        loop.close()
                    
                    full_response = result['response']
                    
                    # Show tool calls if any
                    if result['tool_calls']:
                        tool_info = f"\n\n---\n**🔧 Tools Used:** {len(result['tool_calls'])}\n"
                        for i, tc in enumerate(result['tool_calls'], 1):
                            tool_info += f"\n{i}. `{tc.function.name}()`"
                        full_response += tool_info
                    
                    message_placeholder.markdown(full_response)
                    
                except Exception as e:
                    error_message = f"❌ MCP Mode error: {str(e)}\n\nTry disabling MCP Mode in Advanced Settings."
                    message_placeholder.markdown(error_message)
                    full_response = error_message
                    print(f"ERROR: MCP Mode error: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # Legacy Mode: Original playlist enrichment behavior
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
                        model="gpt-4o-mini",
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

# Handle triggered apply changes (after chat message is shown)
if st.session_state.get('trigger_apply', False):
    st.session_state.trigger_apply = False
    
    # Get AI suggestions from the conversation
    ai_suggestions = None
    if len(st.session_state.messages) > 0:
        for message in reversed(st.session_state.messages):
            if message["role"] == "assistant" and "Applying changes" not in message.get("content", ""):
                ai_suggestions = message["content"]
                break
    
    if ai_suggestions:
        success, message = apply_playlist_changes(
            st.session_state.current_playlist_id, 
            ai_suggestions
        )
        
        st.session_state.applying_changes = False
        
        # Remove the "Applying changes..." message
        if st.session_state.messages and "Applying changes" in st.session_state.messages[-1].get("content", ""):
            st.session_state.messages.pop()
        
        if success:
            # Add success message to chat
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ {message}\n\n🎵 Your playlist has been updated! Use the 'Open in Spotify' button to listen."
            })
            
            # Clear preview after successful apply
            st.session_state.show_preview = False
            st.session_state.preview_data = None
        else:
            # Add error message to chat
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ {message}"
            })
        
        # Save conversation
        if st.session_state.current_user_id and st.session_state.current_playlist_id:
            conversation_manager.save_conversation(st.session_state.current_user_id, st.session_state.current_playlist_id, st.session_state.messages)
        
        st.rerun()

# Control panel moved to bottom of page

# Only stop if not logged in
if st.session_state.token_info is None:
    st.stop()

# Show preview if available
print(f"DEBUG: Checking preview display - show_preview: {st.session_state.get('show_preview', False)}, preview_data exists: {st.session_state.get('preview_data') is not None}")
if st.session_state.get('show_preview', False) and st.session_state.get('preview_data') is not None:
    preview = st.session_state.get('preview_data')
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
                    
                    # Use the properly correlated track results
                    track_results = preview.get('track_results', [])
                    
                    cumulative_time_ms = 0
                    track_counter = 1
                    
                    # Show tracks in AI-recommended order using properly correlated results
                    if track_results:
                        for result in track_results:
                            if result['status'] == 'found':
                                found_track = result['found_track']
                                
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
                                # Track not found - show original AI suggestion
                                track_name = result['original_track_name']
                                artist_name = result['original_artist']
                                
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

# Chat input processing - only when logged in (back to original position)
if st.session_state.token_info is not None:
    if prompt := st.chat_input("Ask me to create a playlist, or chat about music..."):
        st.session_state.pending_prompt = prompt
        st.rerun()

# Fixed bottom container for control buttons only - only when logged in
if st.session_state.token_info is not None:
    
    # Use a placeholder container for the actual control buttons
    bottom_placeholder = st.empty()
    
    with bottom_placeholder.container():
        
        # Playlist Control Panel - Show when conversation is loaded
        if (st.session_state.current_playlist_id and 
            st.session_state.current_playlist_name):
            
            # Control buttons first (above input)
            st.markdown(f"**🎛️ {st.session_state.current_playlist_name}**")
            
            # Initialize session state for preview and apply tracking
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

            # Get AI suggestions from the conversation (use the latest assistant message)
            ai_suggestions = None
            if len(st.session_state.messages) > 0:
                for message in reversed(st.session_state.messages):
                    if message["role"] == "assistant":
                        ai_suggestions = message["content"]
                        break

            # Determine button states
            has_conversation = len(st.session_state.messages) > 1
            has_ai_suggestions = ai_suggestions is not None

            # Show all 5 buttons
            button_col1, button_col2, button_col3, button_col4, button_col5 = st.columns(5)

            with button_col1:
                # Open in Spotify button - always enabled
                spotify_url = f"https://open.spotify.com/playlist/{st.session_state.current_playlist_id}"
                # Use HTML link with target="_blank" to open in new tab
                st.markdown(f"""
                    <a href="{spotify_url}" target="_blank" style="
                        display: inline-block;
                        padding: 0.5rem 1rem;
                        background-color: #1DB954;
                        color: white;
                        text-decoration: none;
                        border-radius: 0.5rem;
                        width: 100%;
                        text-align: center;
                        box-sizing: border-box;
                        font-size: 14px;
                        font-weight: 400;
                        transition: all 0.2s;
                    " onmouseover="this.style.backgroundColor='#1ed760'" 
                       onmouseout="this.style.backgroundColor='#1DB954'"
                       title="Open in Spotify">
                        🎧 Spotify
                    </a>
                """, unsafe_allow_html=True)

            with button_col2:
                # Preview button
                is_disabled = (st.session_state.generating_preview or 
                             st.session_state.applying_changes or 
                             not has_ai_suggestions)
                
                if st.session_state.generating_preview:
                    button_text = "📋 Generating..."
                else:
                    button_text = "👀 Preview"
                
                if st.button(button_text, disabled=is_disabled, use_container_width=True):
                    st.session_state.generating_preview = True
                    st.rerun()

            with button_col3:
                # Apply button - only enabled after preview is generated
                import time
                current_time = time.time()
                time_since_last_apply = current_time - st.session_state.last_apply_time
                can_apply = time_since_last_apply > 10  # 10 second cooldown
                has_preview = st.session_state.get('show_preview', False) and st.session_state.get('preview_data') is not None
                
                is_disabled = (st.session_state.applying_changes or 
                             st.session_state.generating_preview or 
                             not can_apply or 
                             not has_preview)
                
                if st.session_state.applying_changes:
                    button_text = "⏳ Applying..."
                    help_text = "Currently applying changes..."
                elif st.session_state.generating_preview:
                    button_text = "✅ Apply"
                    help_text = "Please wait for preview to complete"
                elif not has_preview:
                    button_text = "✅ Apply"
                    help_text = "Please generate a preview first using the 'Preview' button"
                elif not can_apply:
                    remaining_time = int(10 - time_since_last_apply)
                    button_text = "✅ Apply"
                    help_text = f"⏰ Please wait {remaining_time} seconds before applying again"
                else:
                    button_text = "✅ Apply"
                    help_text = f"Apply the previewed changes to '{st.session_state.current_playlist_name}'"
                
                if st.button(button_text, 
                            type="primary", 
                            use_container_width=True,
                            help=help_text,
                            disabled=is_disabled):
                    
                    st.session_state.applying_changes = True
                    st.session_state.last_apply_time = current_time
                    
                    # Add a chat message instead of spinner
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "⏳ Applying changes to your Spotify playlist..."
                    })
                    
                    # Set flag to trigger apply on next rerun
                    st.session_state.trigger_apply = True
                    st.rerun()

            with button_col4:
                # Reset Conversation button - enabled when conversation exists
                is_disabled = (st.session_state.applying_changes or 
                             st.session_state.generating_preview or 
                             not has_conversation)
                
                if not has_conversation:
                    help_text = "No conversation to reset"
                else:
                    help_text = f"Clear conversation history for '{st.session_state.current_playlist_name}' and start fresh"
                
                if st.button("🔄 Reset", 
                            type="secondary",
                            use_container_width=True,
                            help=help_text,
                            disabled=is_disabled):
                    
                    # Delete the conversation file
                    success = conversation_manager.delete_conversation(
                        st.session_state.current_user_id, 
                        st.session_state.current_playlist_id
                    )
                    
                    if success:
                        st.success("Conversation reset!")
                    else:
                        st.info("No conversation history to reset")
                    
                    # Clear current messages in session and recreate fresh conversation
                    st.session_state.messages = []
                    
                    # Add system message for playlist enrichment specialist
                    system_message = ai_manager.generate_system_message(has_spotify_connection=True)
                    st.session_state.messages.append({
                        "role": "system",
                        "content": system_message
                    })
                    
                    # Add welcome message
                    welcome_message = f"🎵 **Analyzing playlist: {st.session_state.current_playlist_name}**\n\nI'm ready to intelligently enrich this playlist! I can analyze track-to-track transitions, insert new songs at optimal positions within your existing structure, and create smooth musical bridges between contrasting tracks. I'll explain exactly where each new track should go and why it improves the flow. What would you like me to enhance?"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": welcome_message
                    })
                    
                    # Clear any preview state
                    st.session_state.show_preview = False
                    st.session_state.preview_data = None
                    st.session_state.applying_changes = False
                    st.session_state.generating_preview = False
                    
                    st.rerun()

            with button_col5:
                # Clear/Cancel button - enabled when AI suggestions exist
                is_disabled = (st.session_state.applying_changes or 
                             st.session_state.generating_preview or 
                             not has_ai_suggestions)
                
                if not has_ai_suggestions:
                    help_text = "No AI suggestions to clear"
                else:
                    help_text = "Clear current AI suggestions and start over"
                
                if st.button("❌ Clear", 
                            type="secondary",
                            use_container_width=True,
                            help=help_text,
                            disabled=is_disabled):
                    
                    # Clear any AI suggestions by removing the last AI response
                    if st.session_state.messages and st.session_state.messages[-1].get('role') == 'assistant':
                        st.session_state.messages.pop()
                        
                        # Save the updated conversation
                        conversation_manager.save_conversation(
                            st.session_state.current_user_id,
                            st.session_state.current_playlist_id,
                            st.session_state.messages
                        )
                    
                    # Clear any preview state
                    st.session_state.show_preview = False
                    st.session_state.preview_data = None
                    st.session_state.applying_changes = False
                    st.session_state.generating_preview = False
                    
                    st.success("AI suggestions cleared!")
                    st.rerun()

            # Handle preview generation after button click
            if st.session_state.generating_preview:
                success, message, preview_data = preview_playlist_changes(
                    st.session_state.current_playlist_id, 
                    ai_suggestions
                )
                
                st.session_state.generating_preview = False
                
                if success:
                    st.session_state.show_preview = True
                    st.session_state.preview_data = preview_data
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
                    st.rerun()

# Footer
st.markdown("**Jemya** - Your AI-powered Spotify playlist generator 🎵✨")