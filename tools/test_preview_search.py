#!/usr/bin/env python3
"""
Test Preview Search Functionality

This script tests the search functionality used in the preview to see if it's working correctly.
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

def test_preview_search():
    """Test the exact same search logic used in preview_playlist_changes"""
    
    # Get Spotify client
    sp = get_spotify_client()
    if not sp:
        print("❌ Failed to create Spotify client")
        return
    
    # Initialize SpotifyManager (same as in app.py)
    spotify_manager = SpotifyManager()
    
    # Test track that we know works
    track_name = "Prelude in G Minor, Op. 23 No. 5"
    artist_name = "Sergei Rachmaninoff, Sviatoslav Richter"
    
    print(f"🔍 Testing preview search logic...")
    print(f"Track: '{track_name}'")
    print(f"Artist: '{artist_name}'")
    print("=" * 80)
    
    # Use the exact same search call as in preview_playlist_changes
    found_track = spotify_manager.search_track_with_flexible_matching(sp, track_name, artist_name)
    
    if found_track:
        print("✅ SEARCH SUCCESSFUL!")
        print(f"Found: '{found_track['name']}'")
        artists_str = ', '.join([artist['name'] for artist in found_track['artists']])
        print(f"Artists: {artists_str}")
        print(f"Album: {found_track['album']['name']}")
        print(f"Spotify ID: {found_track['id']}")
        print(f"Duration: {found_track['duration_ms']}ms")
        print(f"Spotify URL: {found_track['external_urls'].get('spotify', 'N/A')}")
        
        # Test the preview table data structure creation
        preview_track = {
            'name': found_track['name'],
            'artists': ', '.join([artist['name'] for artist in found_track['artists']]),
            'album': found_track['album']['name'],
            'duration_ms': found_track['duration_ms'],
            'spotify_url': found_track['external_urls'].get('spotify', ''),
            'is_new': True
        }
        
        print("\n📋 Preview track data structure:")
        for key, value in preview_track.items():
            print(f"  {key}: {value}")
        
        # Test the matching logic used in the preview table
        print("\n🔍 Testing preview table matching logic...")
        
        # Simulate original suggestion
        original_suggestion = {
            'track_name': track_name,
            'artist': artist_name
        }
        
        # Test the matching conditions used in app.py lines 1130-1135
        found_match = False
        if (track_name.lower() in found_track['name'].lower() or 
            found_track['name'].lower() in track_name.lower()):
            found_match = True
            print("✅ MATCHING LOGIC WORKS!")
            print(f"Original: '{track_name}'")
            print(f"Found: '{found_track['name']}'")
        else:
            print("❌ MATCHING LOGIC FAILED!")
            print(f"Original: '{track_name}'")
            print(f"Found: '{found_track['name']}'")
            print("This would show as 'Not Found' in the preview table")
        
        return found_match
        
    else:
        print("❌ SEARCH FAILED!")
        print("This track would be added to not_found_tracks")
        return False

def test_multiple_tracks():
    """Test multiple tracks to see pattern"""
    
    test_tracks = [
        ("Prelude in G Minor, Op. 23 No. 5", "Sergei Rachmaninoff, Sviatoslav Richter"),
        ("Clair de Lune", "Claude Debussy"),
        ("Waltz for Debby", "Bill Evans Trio"),
        ("La Vie en Rose", "Édith Piaf"),
    ]
    
    print("\n" + "=" * 80)
    print("🧪 TESTING MULTIPLE TRACKS")
    print("=" * 80)
    
    sp = get_spotify_client()
    if not sp:
        return
    
    spotify_manager = SpotifyManager()
    
    for i, (track_name, artist_name) in enumerate(test_tracks, 1):
        print(f"\n[{i}/{len(test_tracks)}] Testing: '{track_name}' by '{artist_name}'")
        print("-" * 60)
        
        found_track = spotify_manager.search_track_with_flexible_matching(sp, track_name, artist_name)
        
        if found_track:
            print(f"✅ Found: '{found_track['name']}'")
            
            # Test matching logic
            if (track_name.lower() in found_track['name'].lower() or 
                found_track['name'].lower() in track_name.lower()):
                print("✅ Preview table would show: FOUND")
            else:
                print("❌ Preview table would show: NOT FOUND (due to matching logic)")
                print(f"   Original: '{track_name}'")
                print(f"   Found: '{found_track['name']}'")
        else:
            print("❌ Not found by search")

if __name__ == "__main__":
    print("🔍 Preview Search Logic Tester")
    print("=" * 50)
    
    # Test single track first
    success = test_preview_search()
    
    # Test multiple tracks
    test_multiple_tracks()
    
    print("\n" + "=" * 50)
    print("Done! 👋")