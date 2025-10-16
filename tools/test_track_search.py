#!/usr/bin/env python3
"""
Test script to debug track search functionality
This script will test the search logic for all 28 tracks from the AI-generated playlist
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import configuration_manager as conf
import json
from typing import Dict, List, Any

# Sample 28-track playlist from AI
test_tracks = [
    {"track_name": "Keyboard Concerto No. 1 in D Minor, BWV 1052: II. Adagio", "artist": "Johann Sebastian Bach"},
    {"track_name": "Andras", "artist": "Avishai Cohen"},
    {"track_name": "Recuerdos de la Alhambra", "artist": "Francisco Tarrega, Pepe Romero"},
    {"track_name": "Clair de Lune", "artist": "Claude Debussy"},
    {"track_name": "Piano Sonata No. 14 \"Moonlight\": I. Adagio sostenuto", "artist": "Ludwig van Beethoven"},
    {"track_name": "La Vie En Rose", "artist": "Louis Armstrong"},
    {"track_name": "Nuages", "artist": "Django Reinhardt"},
    {"track_name": "Hava Nagila", "artist": "To Life"},
    {"track_name": "Gracias a La Vida", "artist": "Inti-Illimani"},
    {"track_name": "Ave Verum Corpus, K. 618", "artist": "Wolfgang Amadeus Mozart"},
    {"track_name": "Liebesleid", "artist": "Fritz Kreisler"},
    {"track_name": "Humoresque No. 7, Op. 101", "artist": "Antonín Dvořák"},
    {"track_name": "Michelle", "artist": "The Beatles, Violin"},
    {"track_name": "Solfeggietto", "artist": "C.P.E. Bach"},
    {"track_name": "Prelude, Op. 11 No. 15", "artist": "Skrjabin"},
    {"track_name": "Arnica Montana", "artist": "Michel Petrucciani"},
    {"track_name": "Air on the G String", "artist": "The Swingle Singers"},
    {"track_name": "Winter (From \"The Four Seasons\")", "artist": "Max Richter"},
    {"track_name": "Kiss From a Rose (Instrumental)", "artist": "Midnight String Quartet"},
    {"track_name": "Tord Gustavsen Trio - Being There", "artist": "Tord Gustavsen Trio"},
    {"track_name": "Nocturne In E-Flat Major, Op. 9, No. 2", "artist": "Yundi"},
    {"track_name": "Meditation from Thaïs", "artist": "Jules Massenet, Itzhak Perlman"},
    {"track_name": "Le Temps des Cerises", "artist": "Barbara"},
    {"track_name": "Song for the Journey", "artist": "Dirk Maassen"},
    {"track_name": "Gymnopedie No. 1", "artist": "Erik Satie"},
    {"track_name": "Windmills of Your Mind (Instrumental)", "artist": "Earl Klugh"},
    {"track_name": "Inner Peace", "artist": "Brian Crain"},
    {"track_name": "Aria", "artist": "Glenn Gould"}
]

def get_spotify_client():
    """Get authenticated Spotify client"""
    sp_oauth = SpotifyOAuth(
        client_id=conf.SPOTIFY_CLIENT_ID,
        client_secret=conf.SPOTIFY_CLIENT_SECRET,
        redirect_uri=conf.SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state"
    )
    
    # You'll need to handle authentication - for testing, you might need to use cached token
    # or implement a simple auth flow
    token_info = sp_oauth.get_cached_token()
    if not token_info:
        print("No cached token found. You may need to authenticate first.")
        auth_url = sp_oauth.get_authorize_url()
        print(f"Please visit this URL: {auth_url}")
        response = input("Enter the URL you were redirected to: ")
        code = sp_oauth.parse_response_code(response)
        token_info = sp_oauth.get_access_token(code)
    
    return spotipy.Spotify(auth=token_info['access_token'])

def test_search_strategies(sp, track_name, artist_name):
    """Test all search strategies for a single track"""
    print(f"\n{'='*80}")
    print(f"TESTING: {track_name} - {artist_name}")
    print(f"{'='*80}")
    
    found_track = None
    successful_strategy = None
    
    # Define search strategies (same as in spotify_manager.py - now with 18 strategies!)
    search_strategies = [
        # Strategy 1: Exact search with quotes
        f"track:\"{track_name}\" artist:\"{artist_name}\"",
        # Strategy 2: Search without quotes
        f"track:{track_name} artist:{artist_name}",
        # Strategy 3: Simple combined search
        f"\"{track_name}\" \"{artist_name}\"",
        # Strategy 4: Just track and artist names without field operators
        f"{track_name} {artist_name}",
        # Strategy 5: Try with first artist only if comma-separated
        f"{track_name} {artist_name.split(',')[0].strip()}" if ',' in artist_name else None,
        # Strategy 6: Just track name with quotes
        f"\"{track_name}\"",
        # Strategy 7: Track name with classical terms
        f"{track_name} classical" if any(word in track_name.lower() for word in ['concerto', 'sonata', 'prelude', 'nocturne', 'gymnopedie']) else None,
        # Strategy 8: Track name with jazz terms
        f"{track_name} jazz" if any(word in artist_name.lower() for word in ['django', 'louis', 'armstrong', 'reinhardt']) else None,
        # Strategy 9: Final fallback - just track name without quotes
        f"{track_name}",
        # Strategy 10: Track name without instrumental suffixes
        track_name.replace(" (Instrumental)", "").replace(" - Instrumental", "").strip() if any(suffix in track_name for suffix in [" (Instrumental)", " - Instrumental"]) else None
    ]
    
    # Remove None strategies
    search_strategies = [s for s in search_strategies if s is not None]
    
    for i, search_query in enumerate(search_strategies, 1):
        print(f"\nStrategy {i}: {search_query}")
        try:
            results = sp.search(q=search_query, type='track', limit=5)
            
            if results['tracks']['items']:
                print(f"  Found {len(results['tracks']['items'])} results:")
                
                for j, candidate in enumerate(results['tracks']['items'], 1):
                    candidate_name = candidate['name']
                    candidate_artists = ', '.join([artist['name'] for artist in candidate['artists']])
                    
                    print(f"    {j}. '{candidate_name}' by '{candidate_artists}'")
                    
                    # Test matching logic
                    candidate_name_lower = candidate_name.lower()
                    candidate_artists_lower = ' '.join([artist['name'].lower() for artist in candidate['artists']])
                    
                    # Check if this is a good match
                    name_match = (track_name.lower() in candidate_name_lower or 
                                candidate_name_lower in track_name.lower() or
                                # Check for partial matches for long classical titles
                                any(word in candidate_name_lower for word in track_name.lower().split() if len(word) > 3))
                    
                    artist_match = (artist_name.lower() in candidate_artists_lower or
                                  candidate_artists_lower in artist_name.lower() or
                                  # Check for partial artist matches
                                  any(artist.strip().lower() in candidate_artists_lower 
                                      for artist in artist_name.split(',') if len(artist.strip()) > 2))
                    
                    print(f"       Name match: {name_match}, Artist match: {artist_match}")
                    
                    if name_match and artist_match and not found_track:
                        found_track = candidate
                        successful_strategy = f"Strategy {i}"
                        print(f"       ✅ MATCHED! Using this track.")
                        break
                
                if found_track:
                    break
            else:
                print("  No results found")
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    if found_track:
        print(f"\n✅ SUCCESS with {successful_strategy}")
        print(f"   Selected: '{found_track['name']}' by '{', '.join([artist['name'] for artist in found_track['artists']])}'")
        print(f"   URI: {found_track['uri']}")
        return True
    else:
        print(f"\n❌ FAILED - No suitable match found")
        return False

def test_all_tracks():
    """Test search for all tracks"""
    print("🎵 TRACK SEARCH TEST SCRIPT")
    print("=" * 80)
    
    try:
        sp = get_spotify_client()
        print("✅ Spotify client authenticated successfully")
    except Exception as e:
        print(f"❌ Failed to authenticate Spotify client: {e}")
        return
    
    found_count = 0
    not_found_tracks = []
    
    for i, track in enumerate(test_tracks, 1):
        track_name = track['track_name']
        artist_name = track['artist']
        
        print(f"\n[{i}/{len(test_tracks)}] Testing track...")
        success = test_search_strategies(sp, track_name, artist_name)
        
        if success:
            found_count += 1
        else:
            not_found_tracks.append(f"{track_name} - {artist_name}")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total tracks tested: {len(test_tracks)}")
    print(f"Found: {found_count}")
    print(f"Not found: {len(not_found_tracks)}")
    print(f"Success rate: {(found_count/len(test_tracks)*100):.1f}%")
    
    if not_found_tracks:
        print(f"\n❌ Tracks not found:")
        for track in not_found_tracks:
            print(f"  - {track}")
    
    # Save detailed results
    results = {
        'total_tracks': len(test_tracks),
        'found_count': found_count,
        'not_found_count': len(not_found_tracks),
        'success_rate': found_count/len(test_tracks)*100,
        'not_found_tracks': not_found_tracks
    }
    
    with open('track_search_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Detailed results saved to 'track_search_results.json'")

if __name__ == "__main__":
    test_all_tracks()