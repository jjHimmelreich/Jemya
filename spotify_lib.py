import spotipy
from spotipy.oauth2 import SpotifyOAuth
import openai
import json
import os
from datetime import datetime
import conf

# Load environment variables
SPOTIPY_CLIENT_ID = conf.CLIENT_ID
SPOTIPY_CLIENT_SECRET = conf.CLIENT_SECRET
SPOTIPY_REDIRECT_URI = conf.REDIRECT_URI
OPENAI_API_KEY = conf.OPENAI_API_KEY

# Spotify OAuth setup
sp_oauth = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-library-read playlist-modify-public playlist-modify-private"
)

# OpenAI setup
openai.api_key = OPENAI_API_KEY


def get_auth_url():
    """Generate Spotify login URL for OAuth"""
    auth_url = sp_oauth.get_authorize_url()
    return auth_url


def exchange_code(code):
    """Exchange authorization code for access token"""
    token_info = sp_oauth.get_access_token(code)
    return token_info


def get_user_id(token_info):
    """Get Spotify user ID from token info"""
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_info = sp.current_user()
    return user_info['id']


def generate_playlist(token_info, gpt_response):
    """
    Generate a Spotify playlist from GPT response
    :param token_info: Spotify token info (access token, refresh token)
    :param gpt_response: GPT response to create playlist (e.g., genre, mood, activity)
    :return: playlist URL and tracks list
    """
    # Create a Spotify session
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Parse GPT response (expecting a list of genres/moods or specific tracks)
    tracks = []
    if isinstance(gpt_response, str):
        # Example response: "Create a playlist for chill evening vibes"
        query = gpt_response + " music tracks"
        results = sp.search(query, limit=10, type='track')

        for track in results['tracks']['items']:
            tracks.append({
                'title': track['name'],
                'artist': track['artists'][0]['name'],
                'uri': track['uri']
            })

    # Create playlist
    playlist_name = f"GPT Playlist - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    playlist = sp.user_playlist_create(sp.current_user()['id'], playlist_name, public=True)
    
    # Add tracks to playlist
    track_uris = [track['uri'] for track in tracks]
    sp.user_playlist_add_tracks(sp.current_user()['id'], playlist['id'], track_uris)

    # Return playlist URL and track details
    playlist_url = playlist['external_urls']['spotify']
    return playlist_url, tracks


def save_conversation(user_id, gpt_response, playlist_url, tracks):
    """Save conversation to JSON file"""
    # Get current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    # Create file path
    user_folder = f'./conversations/{user_id}'
    os.makedirs(user_folder, exist_ok=True)
    
    # Define conversation structure
    conversation = {
        'user_id': user_id,
        'conversation_id': timestamp,
        'messages': [
            {'role': 'user', 'content': gpt_response},
            {'role': 'gpt', 'content': f"Here’s your playlist: {playlist_url}"},
            {'role': 'spotify', 'playlist_url': playlist_url, 'tracks': tracks}
        ]
    }
    
    # Save conversation to JSON file
    file_path = os.path.join(user_folder, f"{timestamp}.json")
    with open(file_path, 'w') as json_file:
        json.dump(conversation, json_file, indent=4)

    return file_path
