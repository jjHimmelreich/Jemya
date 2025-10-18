#!/usr/bin/env python3
"""
Track Search Debugger for Jemya

This script tests individual tracks using Jemya's actual SpotifyManager implementation.
Shows how search strategies work and what results are returned.

Usage:
    python3 track_debugger.py
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import configuration_manager as conf
from spotify_manager import SpotifyManager

def get_spotify_client():
    """Create Spotify client for searching using client credentials"""
    try:
        client_credentials_manager = SpotifyClientCredentials(
            client_id=conf.SPOTIFY_CLIENT_ID,
            client_secret=conf.SPOTIFY_CLIENT_SECRET
        )
        return spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    except (spotipy.SpotifyException, ValueError) as e:
        print(f"❌ Error creating Spotify client: {e}")
        return None

def test_track_with_jemya_search(track_name, artist_name, spotify_client):
    """Test a track using Jemya's actual search implementation"""
    spotify_manager = SpotifyManager()
    
    print(f"\n🔍 TESTING JEMYA'S ACTUAL SEARCH:")
    print(f"   Track: '{track_name}'")
    print(f"   Artist: '{artist_name}'")
    print("=" * 80)
    
    # Use the actual Jemya search function
    result = spotify_manager.search_track_with_flexible_matching(spotify_client, track_name, artist_name)
    
    if result:
        artists_str = ', '.join([artist['name'] for artist in result['artists']])
        print(f"✅ FOUND: '{result['name']}' by '{artists_str}'")
        print(f"   Spotify ID: {result['id']}")
        print(f"   Preview: {result.get('preview_url', 'Not available')}")
        return result
    else:
        print("❌ NOT FOUND")
        return None

def test_track_with_ai_fallback(track_name, artist_name, spotify_client):
    """Test a track using Jemya's AI fallback search"""
    spotify_manager = SpotifyManager()
    
    print(f"\n🤖 TESTING AI FALLBACK SEARCH:")
    print(f"   Track: '{track_name}'")
    print(f"   Artist: '{artist_name}'")
    print("=" * 80)
    
    # Use the AI fallback search function directly
    result = spotify_manager.search_track_with_ai_fallback(spotify_client, track_name, artist_name)
    
    if result:
        artists_str = ', '.join([artist['name'] for artist in result['artists']])
        print(f"✅ AI SELECTED: '{result['name']}' by '{artists_str}'")
        print(f"   Spotify ID: {result['id']}")
        print(f"   Preview: {result.get('preview_url', 'Not available')}")
        return result
    else:
        print("❌ AI FOUND NO GOOD MATCHES")
        return None

def search_track_debug(track_name, artist, spotify_client):
    """Search for a track with detailed debugging output using SpotifyManager strategies"""
    spotify_manager = SpotifyManager()
    
    print(f"\n🔍 DETAILED STRATEGY TESTING:")
    print(f"   Track: '{track_name}'")
    print(f"   Artist: '{artist}'")
    print("=" * 80)
    
    # Get strategies from SpotifyManager
    strategies = spotify_manager.generate_search_strategies(track_name, artist)
    print(f"\n📋 GENERATED {len(strategies)} SEARCH STRATEGIES:")
    for i, strategy in enumerate(strategies, 1):
        print(f"   {i}. {strategy}")
    
    print(f"\n🎯 TESTING EACH STRATEGY:")
    print("-" * 80)
    
    for i, strategy in enumerate(strategies, 1):
        print(f"\nStrategy {i}: {strategy}")
        
        try:
            results = spotify_client.search(q=strategy, type='track', limit=10)
            tracks = results['tracks']['items']
            
            print(f"   ✅ Returned {len(tracks)} results")

            for t in tracks:
                artists_str = ', '.join([artist['name'] for artist in t['artists']])
                print(f"      - '{t['name']}' by '{artists_str}'")

            if tracks:
                
                print(f"   🎵 First result:")
                first_track = tracks[0]
                artists_str = ', '.join([artist['name'] for artist in first_track['artists']])
                print(f"      '{first_track['name']}' by '{artists_str}'")
                print(f"      Spotify ID: {first_track['id']}")
                
                # This is what the new simplified search would return
                print(f"   🎉 NEW SEARCH WOULD RETURN THIS AND STOP HERE")
                return first_track
            else:
                print(f"   ❌ No results - continue to next strategy")
        except (spotipy.SpotifyException, ValueError, KeyError) as e:
            print(f"   💥 Error: {e}")
    
    print(f"\n❌ No results found after trying all {len(strategies)} strategies")
    return None

def interactive_mode():
    """Interactive mode for testing individual tracks"""
    spotify_client = get_spotify_client()
    if not spotify_client:
        print("Failed to create Spotify client. Check your credentials.")
        return
    
    print("🎵 Jemya Track Search Debugger")
    print("=" * 50)
    print("Test tracks using Jemya's actual search implementation")
    print("Type 'quit' to exit")
    
    while True:
        print("\n" + "-" * 50)
        track_name = input("\nTrack name: ").strip()
        if track_name.lower() == 'quit':
            break
        
        if not track_name:
            print("Please enter a track name")
            continue
            
        artist = input("Artist: ").strip()
        if not artist:
            print("Please enter an artist name")
            continue
        
        print("\nChoose test type:")
        print("1. Quick test (use Jemya's actual search)")
        print("2. AI fallback test (collect all candidates, let AI choose)")
        print("3. Detailed strategy breakdown")
        
        choice = input("Choice (1, 2, or 3): ").strip()
        
        if choice == "1":
            test_track_with_jemya_search(track_name, artist, spotify_client)
        elif choice == "2":
            test_track_with_ai_fallback(track_name, artist, spotify_client)
        elif choice == "3":
            search_track_debug(track_name, artist, spotify_client)
        else:
            print("Invalid choice, using quick test...")
            test_track_with_jemya_search(track_name, artist, spotify_client)

def test_predefined_tracks():
    """Test some predefined problematic tracks"""
    spotify_client = get_spotify_client()
    if not spotify_client:
        print("Failed to create Spotify client. Check your credentials.")
        return
    
    test_tracks = [
        ("Prelude in G Minor, Op. 23 No. 5", "Sergei Rachmaninoff, Sviatoslav Richter"),
        ("Piano Concerto No. 21 in C Major, K. 467: Andante", "Wolfgang Amadeus Mozart, Vienna Philharmonic, Maurizio Pollini"),
        ("Dance of the Blessed Spirits", "Christoph Willibald Gluck, London Symphony Orchestra, Claudio Abbado"),
        ("Meditation from Thaïs", "Jules Massenet, Joshua Bell, Academy of St. Martin in the Fields"),
        ("Waltz for Debby", "Bill Evans Trio"),
        ("La Vie en Rose", "Édith Piaf, Daniel Varsano"),
    ]
    
    print("🧪 Testing predefined tracks using Jemya's actual search:")
    print("=" * 60)
    
    results = []
    for i, (track_name, artist) in enumerate(test_tracks, 1):
        print(f"\n📋 TRACK {i}/{len(test_tracks)}")
        result = test_track_with_jemya_search(track_name, artist, spotify_client)
        results.append((track_name, artist, result is not None))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    found_count = sum(1 for _, _, found in results if found)
    print(f"   Found: {found_count}/{len(results)} tracks")
    
    if found_count < len(results):
        print("\n❌ Tracks not found:")
        for track, artist, found in results:
            if not found:
                print(f"   • '{track}' by '{artist}'")

def test_predefined_tracks_ai():
    """Test predefined tracks using AI fallback search"""
    spotify_client = get_spotify_client()
    if not spotify_client:
        print("Failed to create Spotify client. Check your credentials.")
        return
    
    test_tracks = [
        ("Prelude in G Minor, Op. 23 No. 5", "Sergei Rachmaninoff, Sviatoslav Richter"),
        ("Piano Concerto No. 21 in C Major, K. 467: Andante", "Wolfgang Amadeus Mozart, Vienna Philharmonic, Maurizio Pollini"),
        ("Dance of the Blessed Spirits", "Christoph Willibald Gluck, London Symphony Orchestra, Claudio Abbado"),
        ("Meditation from Thaïs", "Jules Massenet, Joshua Bell, Academy of St. Martin in the Fields"),
        ("Waltz for Debby", "Bill Evans Trio"),
        ("La Vie en Rose", "Édith Piaf, Daniel Varsano"),
    ]
    
    print("🤖 Testing predefined tracks using AI fallback search:")
    print("=" * 60)
    
    results = []
    for i, (track_name, artist) in enumerate(test_tracks, 1):
        print(f"\n📋 TRACK {i}/{len(test_tracks)}")
        result = test_track_with_ai_fallback(track_name, artist, spotify_client)
        results.append((track_name, artist, result is not None))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 AI FALLBACK SUMMARY:")
    found_count = sum(1 for _, _, found in results if found)
    print(f"   Found: {found_count}/{len(results)} tracks")
    
    if found_count < len(results):
        print("\n❌ Tracks not found:")
        for track, artist, found in results:
            if not found:
                print(f"   • '{track}' by '{artist}'")

def test_batch_ai_search():
    """Test the new batch AI search functionality"""
    spotify_client = get_spotify_client()
    if not spotify_client:
        print("Failed to create Spotify client. Check your credentials.")
        return
    
    spotify_manager = SpotifyManager()
    
    test_tracks = [
        {"track_name": "Prelude in G Minor, Op. 23 No. 5", "artist_name": "Sergei Rachmaninoff, Sviatoslav Richter"},
        {"track_name": "Piano Concerto No. 21 in C Major, K. 467: Andante", "artist_name": "Wolfgang Amadeus Mozart, Vienna Philharmonic, Maurizio Pollini"},
        {"track_name": "Dance of the Blessed Spirits", "artist_name": "Christoph Willibald Gluck, London Symphony Orchestra, Claudio Abbado"},
        {"track_name": "Waltz for Debby", "artist_name": "Bill Evans Trio"},
    ]
    
    print("🚀 Testing BATCH AI search (all tracks in one AI call):")
    print("=" * 60)
    
    # Use the batch AI search
    results = spotify_manager.search_tracks_batch_with_ai_fallback(spotify_client, test_tracks)
    
    print(f"\n📊 BATCH AI RESULTS:")
    found_count = 0
    for i, result in enumerate(results):
        track_data = test_tracks[i]
        track_name = track_data['track_name']
        artist_name = track_data['artist_name']
        
        if result:
            found_count += 1
            artists_str = ', '.join([artist['name'] for artist in result['artists']])
            print(f"✅ {i+1}. '{track_name}' → FOUND: '{result['name']}' by '{artists_str}'")
        else:
            print(f"❌ {i+1}. '{track_name}' → NOT FOUND")
    
    print(f"\n📈 BATCH SUMMARY: {found_count}/{len(test_tracks)} tracks found")
    print("🎯 All tracks processed in a single AI call!")

def main():
    """Main function"""
    print("🎵 Jemya Track Search Debugger")
    print("=" * 40)
    print("Test tracks using Jemya's actual SpotifyManager implementation")
    print("\nOptions:")
    print("1. Interactive mode (test your own tracks)")
    print("2. Test predefined tracks with Jemya's search")
    print("3. Test predefined tracks with AI fallback (individual)")
    print("4. Test BATCH AI search (all tracks in one AI call)")
    print("5. Quit")
    
    while True:
        choice = input("\nChoose option (1-5): ").strip()
        
        if choice == "1":
            interactive_mode()
        elif choice == "2":
            test_predefined_tracks()
        elif choice == "3":
            test_predefined_tracks_ai()
        elif choice == "4":
            test_batch_ai_search()
        elif choice == "5":
            print("Goodbye! 👋")
            break
        else:
            print("❌ Please choose 1, 2, 3, 4, or 5")

if __name__ == "__main__":
    main()