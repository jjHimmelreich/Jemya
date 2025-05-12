import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import json
import os
from datetime import datetime
import conf
import time
import utils

# Load environment variables
SPOTIPY_CLIENT_ID = conf.CLIENT_ID
SPOTIPY_CLIENT_SECRET = conf.CLIENT_SECRET
SPOTIPY_REDIRECT_URI = conf.REDIRECT_URI

# # Spotify OAuth setup
# sp_oauth = SpotifyOAuth(
#     client_id=SPOTIPY_CLIENT_ID,
#     client_secret=SPOTIPY_CLIENT_SECRET,
#     redirect_uri=SPOTIPY_REDIRECT_URI,
#     # scope="user-library-read playlist-modify-public playlist-modify-private"
#     scope="user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state"
# )

def get_spotify_oauth():
    return SpotifyOAuth(client_id=conf.CLIENT_ID, 
                        client_secret=conf.CLIENT_SECRET, 
                        redirect_uri=conf.REDIRECT_URI, 
                        scope="user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state")

def refresh_token(token_info):
    # Check if the token is expired
    if token_info and 'expires_at' in token_info and time.time() > token_info['expires_at']:
        sp_oauth = get_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    return token_info

def init(token_info=None):
    if token_info:
        token_info = refresh_token(token_info)  # Ensure token is fresh
        sp = spotipy.Spotify(auth=token_info['access_token'])
    else:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                             client_id=conf.CLIENT_ID, 
                             client_secret=conf.CLIENT_SECRET))
    return sp

######################################################################

def get_auth_url():
    """Generate Spotify login URL for OAuth"""
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return auth_url


def get_user_id(token_info):
    """Get Spotify user ID from token info"""
    sp = init(token_info)

    user_info = sp.current_user()
    return user_info['id']

def get_user_name(token_info):
    """Get Spotify user name from token info"""
    sp = init(token_info)

    user_info = sp.current_user()
    return user_info['display_name']

def get_user_info(token_info):
    sp = init(token_info)
    user_info = sp.current_user()
    return user_info

######################################################################
def create_playlist(token_info, playlist_name=None):
    # Create a Spotify session
    sp = init(token_info)

    # Create playlist name
    p_name = playlist_name if playlist_name else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    p_name = utils.add_prefix_if_missing('Jemya: ', p_name)

    # Create playlist
    playlist = sp.user_playlist_create(sp.current_user()['id'], p_name, public=True)
    
    # Return playlist URL and track details
    playlist_url = playlist['external_urls']['spotify']
    playlist_id = playlist['id']

    return playlist_url, playlist_id


def generate_playlist(token_info, playlist_name=None, tracks_list=[]):
    """
    Generate a Spotify playlist from list of tracks
    :param token_info: Spotify token info (access token, refresh token)
    :return: playlist URL, ID and tracks list
    """
    # Create a Spotify session
    sp = init(token_info)

    tracks = []
    track_uris = []
    tracks_not_found = []

    for t in tracks_list:
        query = f"track:{t['track_name']} artist:{t['artist']}"
        results = sp.search(q=query, type='track', limit=1)
        if results['tracks']['items']:
            spotify_track = results['tracks']['items'][0]
            track_uri = spotify_track['uri']
            track_uris.append(track_uri)

            tracks.append({'track_name': spotify_track['name'], 
                           'artist': spotify_track['artists'][0]['name'], 
                           'spotify_link': spotify_track['href'],
                           'duration': utils.milliseconds_to_human_readable(spotify_track['duration_ms'])
                           }
                        )
        else:
            tracks_not_found.append(query)


    # Create playlist
    p_name = playlist_name if playlist_name else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    p_name = utils.add_prefix_if_missing('Jemya: ', p_name)

    playlist = sp.user_playlist_create(sp.current_user()['id'], p_name, public=True)
    
    # Add tracks to playlist
    playlist_id = playlist['id']
    sp.user_playlist_add_tracks(sp.current_user()['id'], playlist_id, track_uris)

    # Return playlist URL and track details
    playlist_url = playlist['external_urls']['spotify']
    return playlist_url, playlist_id, tracks

def get_user_playlists(token_info):
    sp = init(token_info)
    playlists = []
    offset = 0
    limit = 50  # Spotify API max limit per request
    
    while True:
        response = sp.current_user_playlists(offset=offset, limit=limit)
        playlists.extend(response['items'])

        if len(response['items']) < limit:
            break  # No more playlists to fetch

        offset += limit  # Move to the next page

    return playlists