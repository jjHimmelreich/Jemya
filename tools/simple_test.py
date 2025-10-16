#!/usr/bin/env python3
"""
Simple Track Search Tester

Quick script to test specific tracks and see if they can be found by Jemya's search system.
"""

# Import the actual search function from spotify_manager
try:
    from spotify_manager import search_track_with_flexible_matching, get_spotify_client_credentials
except ImportError:
    print("❌ Could not import spotify_manager functions")
    print("Make sure you're running this from the Jemya directory")
    exit(1)

def test_track(track_name, artist_name):
    """Test a single track using the actual Jemya search function"""
    print(f"\n🔍 Testing: '{track_name}' by '{artist_name}'")
    print("-" * 60)
    
    # Get Spotify client
    sp = get_spotify_client_credentials()
    if not sp:
        print("❌ Failed to create Spotify client")
        return None
    
    # Use the actual search function from Jemya
    result = search_track_with_flexible_matching(track_name, artist_name, sp)
    
    if result:
        print(f"✅ FOUND: '{result['name']}'")
        artists = ', '.join([artist['name'] for artist in result['artists']])
        print(f"   Artists: {artists}")
        print(f"   Spotify ID: {result['id']}")
        print(f"   Preview: {result.get('preview_url', 'Not available')}")
        return result
    else:
        print("❌ NOT FOUND")
        return None

def main():
    """Main function"""
    print("🎵 Jemya Track Search Tester")
    print("=" * 40)
    print("Test specific tracks using Jemya's actual search function")
    
    # Predefined test tracks (you can modify these)
    test_tracks = [
        ("Prelude in G Minor, Op. 23 No. 5", "Sergei Rachmaninoff, Sviatoslav Richter"),
        ("Piano Concerto No. 21 in C Major, K. 467: Andante", "Wolfgang Amadeus Mozart, Vienna Philharmonic, Maurizio Pollini"),
        ("Waltz for Debby", "Bill Evans Trio"),
        ("La Vie en Rose", "Édith Piaf, Daniel Varsano"),
    ]
    
    print(f"\n📋 Testing {len(test_tracks)} predefined tracks:")
    
    results = []
    for i, (track, artist) in enumerate(test_tracks, 1):
        print(f"\n[{i}/{len(test_tracks)}]", end="")
        result = test_track(track, artist)
        results.append((track, artist, result is not None))
    
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
    
    # Interactive mode
    print(f"\n{'='*60}")
    print("🎯 INTERACTIVE MODE")
    print("Enter your own tracks to test (type 'quit' to exit):")
    
    while True:
        track = input("\nTrack name: ").strip()
        if track.lower() == 'quit':
            break
        if not track:
            continue
            
        artist = input("Artist: ").strip()
        if not artist:
            continue
            
        test_track(track, artist)

if __name__ == "__main__":
    main()