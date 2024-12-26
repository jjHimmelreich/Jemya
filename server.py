import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

import conf

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=conf.CLIENT_ID,
                                                           client_secret=conf.CLIENT_SECRET))

results = sp.search(q='himmelreich', limit=20)
for idx, track in enumerate(results['tracks']['items']):
    print(idx, track['name'])