import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from texttable import Texttable

import conf
import utils


sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=conf.CLIENT_ID,
                                                           client_secret=conf.CLIENT_SECRET))

# results = sp.search(q='himmelreich', limit=20)
# for idx, track in enumerate(results['tracks']['items']):
#     print(idx, track['name'])

results = sp.playlist_items('1OqSCV8pzfAZ6zsAjEsYOM')

tbl = Texttable(max_width=1024)
tbl.header(['Time','Duration','Title', 'Artist'])
tbl.set_deco(Texttable.VLINES | Texttable.HEADER | Texttable.BORDER)
row = []

ttl_duration_ms = 0.1
for idx, track in enumerate(results['items']):
    t = track['track']
    
    names = [artist['name'] for artist in t['artists']]
    artists = ' '.join(names)


    album = t['album']['name']
    name = t['name']
    pop = t['popularity']
    
    t_duration_ms = t['duration_ms']

    # id = t['id']

    # analysis = sp.audio_analysis(id)

    #print (f"{utils.milliseconds_to_human_readable(ttl_duration_ms)} | {name} | {album}")

    tbl.add_row([utils.milliseconds_to_human_readable(ttl_duration_ms),
                 utils.milliseconds_to_human_readable(t_duration_ms),
                 name,
                 artists])

    ttl_duration_ms = t_duration_ms + ttl_duration_ms


print (tbl.draw())
