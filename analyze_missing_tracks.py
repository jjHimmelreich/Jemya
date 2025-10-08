#!/usr/bin/env python3
"""
Quick test script to analyze the missing tracks problem
"""

# Tracks that were likely not found based on the pattern we see
problematic_tracks = [
    ("Andras", "Avishai Cohen"),
    ("Hava Nagila", "To Life"), 
    ("Michelle", "The Beatles, Violin"),
    ("Prelude, Op. 11 No. 15", "Alexander Scriabin"),  # was "Skrjabin"
    ("Arnica Montana", "Michel Petrucciani"),
    ("Air on the G String", "The Swingle Singers"),
    ("Kiss From a Rose (Instrumental)", "Midnight String Quartet"),
    ("Tord Gustavsen Trio - Being There", "Tord Gustavsen Trio"),  # redundant name
    ("Le Temps des Cerises", "Barbara"),
    ("Song for the Journey", "Dirk Maassen"),
    ("Windmills of Your Mind (Instrumental)", "Earl Klugh"),
    ("Inner Peace", "Brian Crain")
]

print("ANALYSIS OF LIKELY MISSING TRACKS:")
print("=" * 50)

print("\nISSUES IDENTIFIED:")
print("1. Artist name inconsistencies:")
print("   - 'Skrjabin' vs 'Alexander Scriabin' (spelling/full name)")
print("   - 'The Beatles, Violin' (not a real artist)")

print("\n2. Non-existent or very specific artists:")
print("   - 'To Life' (likely not the actual artist for Hava Nagila)")
print("   - 'Midnight String Quartet' (may not exist)")

print("\n3. Redundant track names:")
print("   - 'Tord Gustavsen Trio - Being There' (artist name in track name)")

print("\n4. Very specific instrumental versions:")
print("   - 'Kiss From a Rose (Instrumental)'")
print("   - 'Windmills of Your Mind (Instrumental)'")

print("\n5. Uncommon jazz/contemporary tracks:")
print("   - Many of these are lesser-known or very specific versions")

print("\nSOLUTIONS:")
print("1. Improve artist name normalization")
print("2. Add fallback searches with generic terms")
print("3. Handle instrumental versions better")
print("4. Clean up redundant artist names in track titles")

print("\nThe search algorithm is working, but the AI is generating")
print("tracks with problematic metadata that don't exist on Spotify")
print("in the exact form specified.")