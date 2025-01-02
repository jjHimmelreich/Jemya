import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from texttable import Texttable

pattern = r'playlist/([a-zA-Z0-9]+)'

import conf
import utils

#https://open.spotify.com/playlist/5gmv8rah3E1YMMT1tGgUW0?si=99f17988b5df4353
def process_playlist(playlist_link):

    track_objects = []

    #playlist_link = input(f"Paste link to playlist here:")
    
    # Search for the pattern in the input string
    match = re.search(pattern, playlist_link)
    playlist_id = None

    # Extract the playlist ID
    if match:
        playlist_id = match.group(1)

    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=conf.CLIENT_ID,
                                                            client_secret=conf.CLIENT_SECRET))

    playlist = sp.playlist(playlist_id)

    playlist_name = playlist['name']


    #results = sp.playlist_items(playlist_id)
    tracks = playlist['tracks']['items']

    tbl = Texttable(max_width=1024)
    tbl.header(['Time','Duration','Title', 'Artist'])
    tbl.set_deco(Texttable.VLINES | Texttable.HEADER | Texttable.BORDER)
    row = []

    ttl_duration_ms = 0.1
    for idx, track in enumerate(tracks):
        t = track['track']
        
        names = [artist['name'] for artist in t['artists']]
        artists = ', '.join(names)

        album = t['album']['name']
        name = t['name']
        pop = t['popularity']

        id = t['id']
        track_url = f'https://open.spotify.com/track/{id}'
        
        t_duration_ms = t['duration_ms']

        ttl_duration_ms = t_duration_ms + ttl_duration_ms

        track_objects.append(
            {
                "idx":idx,
                "id": id,
                "url":track_url,
                "name": name,
                "album": album,
                "author": artists,
                "duration": utils.milliseconds_to_human_readable(t_duration_ms),
                "duration_from_start": utils.milliseconds_to_human_readable(ttl_duration_ms)
            }
        )

    return playlist_name,track_objects
