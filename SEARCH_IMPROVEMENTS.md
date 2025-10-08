# Track Search Improvement Summary

## Problem Analysis
- AI generates 28 tracks but only 17-18 are found
- Issues identified:
  1. **Bad AI-generated metadata**:
     - Non-existent artists: "To Life", "Midnight String Quartet"
     - Misspelled names: "Skrjabin" vs "Alexander Scriabin" 
     - Impossible combinations: "The Beatles, Violin"
     - Redundant naming: "Tord Gustavsen Trio - Being There" by "Tord Gustavsen Trio"

  2. **Search algorithm limitations**:
     - Too restrictive exact matching
     - Didn't handle variations well
     - No fallback for problematic metadata

## Improvements Made

### 1. Track Name Cleaning
```python
# Remove artist name if redundantly included in track name
if artist_name.lower() in track_name.lower():
    # Remove artist name from track name
    clean_track_name = remove_artist_from_track_name(track_name, artist_name)
```

### 2. Artist Name Corrections
```python
artist_corrections = {
    'skrjabin': 'scriabin',
    'skryabin': 'scriabin', 
    'the beatles, violin': 'the beatles',
    'to life': '',  # Often wrong for Hava Nagila
}
```

### 3. Enhanced Search Strategies (14 total)
1. Exact search with quotes (original)
2. Exact search with quotes (cleaned)
3. Search without quotes (original)
4. Search without quotes (cleaned)
5. Simple combined search (original)
6. Simple combined search (cleaned)
7. Track + artist names (original)
8. Track + artist names (cleaned)
9. First artist only (original)
10. First artist only (cleaned)
11. Just track name
12. Just cleaned track name
13. Track name + "classical" (for classical pieces)
14. Track name + "jazz" (for jazz pieces)

### 4. Improved Matching Logic
- **Flexible name matching**: Handles partial matches, removes common suffixes like "(instrumental)"
- **Better artist matching**: Handles comma-separated artists, partial matches
- **Fallback matching**: For problematic artists, accepts close track name matches

### 5. Expected Results
With these improvements, we should find **22-25 out of 28 tracks** instead of just 17-18.

The remaining unfound tracks will likely be:
- Completely non-existent recordings
- Very rare/specific versions not on Spotify
- Tracks with completely wrong metadata from AI

## Testing
Run the main app and generate a new playlist to test the improvements.
The debug output will show which search strategy succeeded for each track.