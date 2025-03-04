import utils
import conf
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from texttable import Texttable
pattern = r'playlist/([a-zA-Z0-9]+)'


def get_spotify_oauth():
    return SpotifyOAuth(client_id=conf.CLIENT_ID, 
                        client_secret=conf.CLIENT_SECRET, 
                        redirect_uri=conf.REDIRECT_URI, 
                        scope="playlist-modify-public playlist-modify-private user-modify-playback-state user-read-playback-state")


def init(token_info=None):
    if token_info:
        sp = spotipy.Spotify(auth=token_info['access_token'])
    else:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                             client_id=conf.CLIENT_ID, 
                             client_secret=conf.CLIENT_SECRET))
    return sp


def get_user_info(token_info):
    sp = init(token_info)
    user_info = sp.current_user()
    return user_info

def get_user_playlists(token_info):
    sp = init(token_info)
    playlists = sp.current_user_playlists()
    return playlists['items']

def get_playlist_tracks(playlist_id, token_info):
    sp = init(token_info)
    results = sp.playlist_tracks(playlist_id)
    track_objects = []
    ttl_duration_ms = 0.1
    for idx, item in enumerate(results['items']):
        track = item['track']
        names = [artist['name'] for artist in track['artists']]
        artists = ', '.join(names)
        album = track['album']['name']
        name = track['name']
        id = track['id']
        track_url = track['external_urls']['spotify']
        album_image = track['album']['images'][0]['url']
        t_duration_ms = track['duration_ms']
        ttl_duration_ms = t_duration_ms + ttl_duration_ms
        track_objects.append(
            {
                "idx": idx + 1,  # Track number starts from 1
                "id": id,
                "url": track_url,
                "name": name,
                "album": album,
                "album_image_url": album_image,
                "author": artists,
                "duration": utils.milliseconds_to_human_readable(t_duration_ms),
                "duration_from_start": utils.milliseconds_to_human_readable(ttl_duration_ms - t_duration_ms)
            }
        )
    total_duration = utils.milliseconds_to_human_readable(ttl_duration_ms)
    return track_objects, len(track_objects), total_duration

def process_playlist(playlist_link):
    track_objects = []
    match = re.search(pattern, playlist_link)
    playlist_id = None
    if match:
        playlist_id = match.group(1)
    sp = init()  # No token_info needed for fetching playlist details
    playlist = sp.playlist(playlist_id)
    playlist_name = playlist['name']
    tracks = playlist['tracks']['items']
    ttl_duration_ms = 0.1
    for idx, track in enumerate(tracks):
        t = track['track']
        names = [artist['name'] for artist in t['artists']]
        artists = ', '.join(names)
        album = t['album']['name']
        name = t['name']
        pop = t['popularity']
        id = t['id']
        track_url = t['external_urls']['spotify']
        album_image = t['album']['images'][0]['url']
        t_duration_ms = t['duration_ms']
        ttl_duration_ms = t_duration_ms + ttl_duration_ms
        track_objects.append(
            {
                "idx": idx,
                "id": id,
                "url": track_url,
                "name": name,
                "album": album,
                "album_image_url": album_image,
                "author": artists,
                "duration": utils.milliseconds_to_human_readable(t_duration_ms),
                "duration_from_start": utils.milliseconds_to_human_readable(ttl_duration_ms - t_duration_ms)
            }
        )
    return playlist_name, track_objects

def clear_playlist(playlist_id, token_info):
    sp = init(token_info)

    # Get the current tracks in the playlist
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    
    # Collect all track URIs
    track_uris = [track['track']['uri'] for track in tracks]
    
    # Remove tracks in batches of 100 (Spotify API limit)
    for i in range(0, len(track_uris), 100):
        sp.playlist_remove_all_occurrences_of_items(playlist_id, track_uris[i:i+100])

def get_playlist_name(playlist_id, token_info):
    sp = init(token_info)
    
    # Get the playlist details
    playlist = sp.playlist(playlist_id)
    # Return the playlist name
    return playlist['name']


def create_playlist(playlist_id, generated_tracks, token_info):
    sp = init(token_info)
    user_id = sp.current_user()['id']

    # Clear playlist
    clear_playlist(playlist_id=playlist_id, token_info=token_info)

    playlist_name = get_playlist_name(playlist_id=playlist_id, token_info=token_info)

    playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=True)
    
    playlist_id = playlist['id']
    track_uris = []
    for track in generated_tracks:
        query = f"track:{track['track_name']} artist:{track['artist']}"
        results = sp.search(q=query, type='track', limit=1)
        if results['tracks']['items']:
            track_uri = results['tracks']['items'][0]['uri']
            track_uris.append(track_uri)
            
    if track_uris:
        sp.user_playlist_add_tracks(
            user=user_id, playlist_id=playlist_id, tracks=track_uris)
    playlist_url = playlist['external_urls']['spotify']
    return playlist_url


def play_track(track_id, token_info):
    sp = init(token_info)
    sp.start_playback(uris=[f'spotify:track:{track_id}'])
    print(f'Playing track: {track_id}')


def pause_track(track_id, token_info):
    sp = init(token_info)
    sp.pause_playback()
    print(f'Pausing track: {track_id}')
