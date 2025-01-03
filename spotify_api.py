import utils
import conf
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from texttable import Texttable
pattern = r'playlist/([a-zA-Z0-9]+)'


def get_spotify_oauth():
    sp = SpotifyOAuth(client_id=conf.CLIENT_ID, client_secret=conf.CLIENT_SECRET, redirect_uri=conf.REDIRECT_URI, scope="user-modify-playback-state user-read-playback-state")
    return sp


def init(token_info=None):
    if token_info:
        sp = spotipy.Spotify(auth=token_info['access_token'])
    else:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=conf.CLIENT_ID, client_secret=conf.CLIENT_SECRET))
    return sp


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


def play_track(track_id, token_info):
    sp = init(token_info)
    sp.start_playback(uris=[f'spotify:track:{track_id}'])
    print(f'Playing track: {track_id}')


def pause_track(track_id, token_info):
    sp = init(token_info)
    sp.pause_playback()
    print(f'Pausing track: {track_id}')
