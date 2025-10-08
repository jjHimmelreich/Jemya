#!/usr/bin/env python3
"""
Simple test script to debug track search issues
Uses existing session state if available
"""

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import conf
import sys
import os

# Add current directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_single_track_search(sp, track_name, artist_name):
    """Test search for a single track with detailed output"""
    print(f"\n{'='*60}")
    print(f"Testing: '{track_name}' by '{artist_name}'")
    print(f"{'='*60}")
    
    # Try multiple search strategies
    strategies = [
        f'track:"{track_name}" artist:"{artist_name}"',
        f'track:{track_name} artist:{artist_name}',
        f'"{track_name}" "{artist_name}"',
        f'{track_name} {artist_name}',
        f'{track_name} {artist_name.split(",")[0].strip()}' if ',' in artist_name else None
    ]
    
    strategies = [s for s in strategies if s is not None]
    
    for i, query in enumerate(strategies, 1):
        print(f"\nStrategy {i}: {query}")
        try:
            results = sp.search(q=query, type='track', limit=3)
            if results['tracks']['items']:
                print(f"  Found {len(results['tracks']['items'])} results:")
                for j, track in enumerate(results['tracks']['items'], 1):
                    artists = ', '.join([a['name'] for a in track['artists']])
                    print(f"    {j}. '{track['name']}' by '{artists}'")
                    
                    # Test our matching logic
                    name_lower = track['name'].lower()
                    artist_lower = ' '.join([a['name'].lower() for a in track['artists']])
                    
                    name_match = (track_name.lower() in name_lower or 
                                 name_lower in track_name.lower() or
                                 any(word in name_lower for word in track_name.lower().split() if len(word) > 3))
                    
                    artist_match = (artist_name.lower() in artist_lower or
                                   artist_lower in artist_name.lower() or
                                   any(artist.strip().lower() in artist_lower 
                                       for artist in artist_name.split(',') if len(artist.strip()) > 2))
                    
                    match_status = "✅ MATCH" if (name_match and artist_match) else "❌ NO MATCH"
                    print(f"       {match_status} (name: {name_match}, artist: {artist_match})")
                    
                    if name_match and artist_match:
                        return True, track
            else:
                print("  No results found")
        except Exception as e:
            print(f"  Error: {e}")
    
    return False, None

def main():
    """Main test function"""
    print("🎵 SPOTIFY TRACK SEARCH DEBUGGER")
    print("=" * 60)
    
    # Get Spotify client using existing token from session
    try:
        # Try to use cached token
        sp_oauth = SpotifyOAuth(
            client_id=conf.CLIENT_ID,
            client_secret=conf.CLIENT_SECRET,
            redirect_uri=conf.REDIRECT_URI,
            scope="user-read-playbook-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playbook-state"
        )
        
        token_info = sp_oauth.get_cached_token()
        if token_info:
            sp = spotipy.Spotify(auth=token_info['access_token'])
            print("✅ Using cached Spotify token")
        else:
            print("❌ No cached token found. Please run the main app first to authenticate.")
            return
    except Exception as e:
        print(f"❌ Failed to get Spotify client: {e}")
        return
    
    # Test some problematic tracks from the list
    test_tracks = [
        ("Andras", "Avishai Cohen"),
        ("Hava Nagila", "To Life"),
        ("Michelle", "The Beatles, Violin"),
        ("Prelude, Op. 11 No. 15", "Alexander Scriabin"),
        ("Arnica Montana", "Michel Petrucciani"),
        ("Air on the G String", "The Swingle Singers"),
        ("Kiss From a Rose (Instrumental)", "Midnight String Quartet"),
        ("Being There", "Tord Gustavsen Trio"),
        ("Le Temps des Cerises", "Barbara"),
        ("Song for the Journey", "Dirk Maassen"),
        ("Windmills of Your Mind (Instrumental)", "Earl Klugh"),
        ("Inner Peace", "Brian Crain"),
    ]
    
    found_count = 0
    total_count = len(test_tracks)
    
    for track_name, artist_name in test_tracks:
        found, track_info = test_single_track_search(sp, track_name, artist_name)
        if found:
            found_count += 1
            print(f"✅ SUCCESS: Using '{track_info['name']}' by '{', '.join([a['name'] for a in track_info['artists']])}'")
        else:
            print(f"❌ FAILED: Could not find '{track_name}' by '{artist_name}'")
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {found_count}/{total_count} tracks found")
    print(f"Success rate: {(found_count/total_count)*100:.1f}%")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()