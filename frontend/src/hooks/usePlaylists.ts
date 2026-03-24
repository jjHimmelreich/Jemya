import { useState, useCallback, useEffect } from 'react';
import { getPlaylists, getYtPlaylists, getPlaylistTracks, getYtPlaylistTracks } from '../api/client';
import type { PlaylistItem, TrackItem, TokenInfo } from '../types';

export function usePlaylists(tokenInfo: TokenInfo | null) {
  const [playlists, setPlaylists] = useState<PlaylistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isYt = tokenInfo?.source === 'youtube';

  const fetchPlaylists = useCallback(async () => {
    if (!tokenInfo) return;
    setLoading(true);
    setError(null);
    try {
      const data = isYt ? await getYtPlaylists(tokenInfo) : await getPlaylists(tokenInfo);
      setPlaylists(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load playlists');
    } finally {
      setLoading(false);
    }
  }, [tokenInfo, isYt]);

  useEffect(() => {
    fetchPlaylists();
  }, [fetchPlaylists]);

  const fetchTracks = useCallback(
    async (playlistId: string): Promise<TrackItem[]> => {
      if (!tokenInfo) return [];
      try {
        return isYt
          ? await getYtPlaylistTracks(tokenInfo, playlistId)
          : await getPlaylistTracks(tokenInfo, playlistId);
      } catch {
        return [];
      }
    },
    [tokenInfo, isYt],
  );

  const updatePlaylistCount = useCallback((playlistId: string, count: number) => {
    setPlaylists((prev) =>
      prev.map((p) => (p.id === playlistId ? { ...p, tracks_total: count } : p)),
    );
  }, []);

  return { playlists, loading, error, fetchPlaylists, fetchTracks, updatePlaylistCount };
}
