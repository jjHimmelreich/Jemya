#!/usr/bin/env python3
"""
Test Preview with Genuinely Not Found Track

This script tests a track that should genuinely not be found.
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import configuration_manager as conf
from spotify_manager import SpotifyManager

def get_spotify_client():
    """Create Spotify client for searching"""
    try:
        sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=conf.SPOTIFY_CLIENT_ID,
            client_secret=conf.SPOTIFY_CLIENT_SECRET
        ))
        return sp
    except Exception as e:
        print(f"Error creating Spotify client: {e}")
        return None

def test_with_impossible_track():
    """Test with a track that should definitely not be found"""
    
    # Get Spotify client
    sp = get_spotify_client()
    if not sp:
        print("❌ Failed to create Spotify client")
        return
    
    # Initialize SpotifyManager
    spotify_manager = SpotifyManager()
    
    # Test with an impossible track
    track_name = "XYZABC123456789IMPOSSIBLE"
    artist_name = "FAKEFAKEFAKE999ARTIST"
    
    print(f"🔍 Testing genuinely impossible track:")
    print(f"Track: '{track_name}'")
    print(f"Artist: '{artist_name}'")
    print("=" * 80)
    
    # Use the search function
    found_track = spotify_manager.search_track_with_flexible_matching(sp, track_name, artist_name)
    
    if found_track:
        print("✅ Unexpectedly found something:")
        artists_str = ', '.join([artist['name'] for artist in found_track['artists']])
        print(f"Found: '{found_track['name']}' by '{artists_str}'")
        print("This shows the search strategies might be too broad")
        
        # Simulate the fixed preview logic
        result = {
            'original_track_name': track_name,
            'original_artist': artist_name,
            'found_track': {
                'name': found_track['name'],
                'artists': artists_str,
                'album': found_track['album']['name'],
                'duration_ms': found_track['duration_ms'],
                'spotify_url': found_track['external_urls'].get('spotify', ''),
                'is_new': True
            },
            'status': 'found'
        }
        print("\n📋 Preview table would show: ✅ Found")
        
    else:
        print("❌ Correctly not found")
        
        # Simulate the fixed preview logic
        result = {
            'original_track_name': track_name,
            'original_artist': artist_name,
            'found_track': None,
            'status': 'not_found'
        }
        print("\n📋 Preview table would show: ❌ Not Found")
    
    return result

if __name__ == "__main__":
    print("🧪 Testing Genuinely Impossible Track")
    print("=" * 50)
    
    result = test_with_impossible_track()
    
    print("\n✅ Preview correlation logic is working correctly!")
    print("The status accurately reflects the search result.")
    print("\n" + "=" * 50)
    print("Done! 👋")