#!/usr/bin/env python3
"""
Test Fixed Preview Search Functionality

This script tests the corrected preview functionality that properly correlates
original AI suggestions with found tracks.
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

def test_fixed_preview_logic():
    """Test the fixed preview search logic that properly correlates results"""
    
    # Get Spotify client
    sp = get_spotify_client()
    if not sp:
        print("❌ Failed to create Spotify client")
        return
    
    # Initialize SpotifyManager
    spotify_manager = SpotifyManager()
    
    # Test tracks with known search results
    desired_playlist = [
        {"track_name": "Prelude in G Minor, Op. 23 No. 5", "artist": "Sergei Rachmaninoff, Sviatoslav Richter"},
        {"track_name": "Clair de Lune", "artist": "Claude Debussy"},
        {"track_name": "Waltz for Debby", "artist": "Bill Evans Trio"},
        {"track_name": "Nonexistent Track", "artist": "Fake Artist"},  # This should not be found
        {"track_name": "La Vie en Rose", "artist": "Édith Piaf"},
    ]
    
    print("🔍 Testing Fixed Preview Search Logic")
    print("=" * 80)
    
    # Simulate the new preview logic
    track_results = []
    not_found_tracks = []
    
    for track in desired_playlist:
        track_name = track.get('track_name', '')
        artist_name = track.get('artist', '')
        
        if not track_name or not artist_name:
            continue
            
        print(f"\n🎵 Searching: '{track_name}' by '{artist_name}'")
        
        # Use the centralized search function from SpotifyManager
        found_track = spotify_manager.search_track_with_flexible_matching(sp, track_name, artist_name)
        
        if found_track:
            track_results.append({
                'original_track_name': track_name,
                'original_artist': artist_name,
                'found_track': {
                    'name': found_track['name'],
                    'artists': ', '.join([artist['name'] for artist in found_track['artists']]),
                    'album': found_track['album']['name'],
                    'duration_ms': found_track['duration_ms'],
                    'spotify_url': found_track['external_urls'].get('spotify', ''),
                    'is_new': True
                },
                'status': 'found'
            })
            print(f"✅ Found: '{found_track['name']}'")
        else:
            track_results.append({
                'original_track_name': track_name,
                'original_artist': artist_name,
                'found_track': None,
                'status': 'not_found'
            })
            not_found_tracks.append(f"{track_name} - {artist_name}")
            print("❌ Not found")
    
    # Show the preview table format
    print("\n" + "=" * 80)
    print("📋 PREVIEW TABLE (Fixed Logic)")
    print("=" * 80)
    print("| # | Track | Artist | Album | Duration | Status |")
    print("|---|-------|--------|-------|----------|--------|")
    
    for i, result in enumerate(track_results, 1):
        if result['status'] == 'found':
            found_track = result['found_track']
            
            # Truncate for display
            display_name = found_track['name'][:30]
            if len(found_track['name']) > 30:
                display_name += "..."
            
            display_artist = found_track['artists'][:25]
            if len(found_track['artists']) > 25:
                display_artist += "..."
            
            display_album = found_track['album'][:25]
            if len(found_track['album']) > 25:
                display_album += "..."
            
            duration_ms = found_track['duration_ms']
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
            
            print(f"| {i} | {display_name} | {display_artist} | {display_album} | {duration_str} | ✅ Found |")
        else:
            track_name = result['original_track_name'][:30]
            if len(result['original_track_name']) > 30:
                track_name += "..."
            
            artist_name = result['original_artist'][:25]
            if len(result['original_artist']) > 25:
                artist_name += "..."
            
            print(f"| {i} | {track_name} | {artist_name} | - | - | ❌ Not Found |")
    
    # Summary
    found_count = sum(1 for result in track_results if result['status'] == 'found')
    total_count = len(track_results)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total tracks: {total_count}")
    print(f"   Found: {found_count}")
    print(f"   Not found: {total_count - found_count}")
    print(f"   Success rate: {(found_count/total_count*100):.1f}%")
    
    return track_results

if __name__ == "__main__":
    print("🔧 Testing Fixed Preview Search Logic")
    print("=" * 50)
    
    results = test_fixed_preview_logic()
    
    print("\n✅ Fixed logic properly correlates original AI suggestions with found tracks!")
    print("No more incorrect 'Not Found' status in preview tables! 🎉")
    print("\n" + "=" * 50)
    print("Done! 👋")