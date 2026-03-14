import { useState, useCallback, useEffect } from 'react';
import { getPlaylists, getPlaylistTracks } from '../api/client';
import type { PlaylistItem, TrackItem, TokenInfo } from '../types';

export function usePlaylists(tokenInfo: TokenInfo | null) {
  const [playlists, setPlaylists] = useState<PlaylistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPlaylists = useCallback(async () => {
    if (!tokenInfo) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPlaylists(tokenInfo);
      setPlaylists(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load playlists');
    } finally {
      setLoading(false);
    }
  }, [tokenInfo]);

  useEffect(() => {
    fetchPlaylists();
  }, [fetchPlaylists]);

  const fetchTracks = useCallback(
    async (playlistId: string): Promise<TrackItem[]> => {
      if (!tokenInfo) return [];
      try {
        return await getPlaylistTracks(tokenInfo, playlistId);
      } catch {
        return [];
      }
    },
    [tokenInfo],
  );

  // Correct the track count for a specific playlist in local state
  // (Spotify's listing endpoint caches tracks.total and can lag behind reality)
  const updatePlaylistCount = useCallback((playlistId: string, count: number) => {
    setPlaylists((prev) =>
      prev.map((p) => (p.id === playlistId ? { ...p, tracks_total: count } : p)),
    );
  }, []);

  return { playlists, loading, error, fetchPlaylists, fetchTracks, updatePlaylistCount };
}
