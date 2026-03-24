import { useState, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { ChatWindow } from '../components/ChatWindow';
import { PreviewModal } from '../components/PreviewModal';
import { ToolsPage } from './ToolsPage';
import { useChat } from '../hooks/useChat';
import { usePlaylists } from '../hooks/usePlaylists';
import { extractTracks, previewChanges, applyChanges, getPlaylistTracks, getYtPlaylistTracks, createPlaylist, loadConversation } from '../api/client';
import type { PlaylistItem, TrackItem, TokenInfo, UserInfo, PreviewData, ApplyResult } from '../types';
import styles from './AppPage.module.css';

function formatTime(ms: number): string {
  if (ms === 0) return '0s';
  const totalMinutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  if (totalMinutes >= 60) {
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  }
  return seconds > 0 ? `${totalMinutes}m ${seconds}s` : `${totalMinutes}m`;
}

function buildTracksTable(playlist: PlaylistItem, tracks: TrackItem[], source?: string): string {
  const ownerName = playlist.owner_name || 'Unknown';
  const isPublic = playlist.public;
  const isYt = source === 'youtube';
  const playlistUrl = isYt
    ? `https://www.youtube.com/playlist?list=${playlist.id}`
    : `https://open.spotify.com/playlist/${playlist.id}`;
  const sourceIcon = isYt ? '' : '![](/spotify-icon.svg) ';
  let table = `## ${sourceIcon}[${playlist.name}](${playlistUrl})\n\n`;
  table += `**Playlist ID:** \`${playlist.id}\`\n`;
  table += `**Created by:** ${ownerName} • **${tracks.length} tracks** • ${isPublic ? 'Public' : 'Private'}\n\n`;

  if (tracks.length === 0) {
    table += "*This playlist is empty. Start adding tracks by telling me what kind of music you'd like!*";
    return table;
  }

  table += '| # | Track | Artist | Album | Duration | Start Time |\n';
  table += '|---|-------|--------|-------|----------|------------|\n';

  let cumulativeMs = 0;
  tracks.forEach((track, i) => {
    const startTime = formatTime(cumulativeMs);
    const duration = formatTime(track.duration_ms || 0);

    let name = (track.name || 'Unknown').substring(0, 40);
    if ((track.name || '').length > 40) name += '...';
    const trackUrl = isYt
      ? (track.uri ? `https://www.youtube.com/watch?v=${track.uri}` : null)
      : (track.spotify_url
        ? `${track.spotify_url}?context=spotify:playlist:${playlist.id}`
        : null);
    const nameDisplay = trackUrl ? `[${name}](${trackUrl})` : name;

    let artist = (track.artists || 'Unknown').substring(0, 30);
    if ((track.artists || '').length > 30) artist += '...';

    let album = (track.album || '').substring(0, 30);
    if ((track.album || '').length > 30) album += '...';

    table += `| ${i + 1} | ${nameDisplay} | ${artist} | ${album} | ${duration} | ${startTime} |\n`;
    cumulativeMs += track.duration_ms || 0;
  });

  const totalMs = tracks.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
  const totalMinutes = Math.floor(totalMs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  const durationSummary = hours > 0 ? `${hours}h ${mins}m` : `${totalMinutes}m`;
  table += `\n**Total duration:** ${durationSummary}\n`;
  return table;
}

interface Props {
  tokenInfo: TokenInfo;
  userInfo: UserInfo | null;
  onLogout: () => void;
  ensureValidToken: () => Promise<TokenInfo | null>;
}

export function AppPage({ tokenInfo, userInfo, onLogout, ensureValidToken }: Props) {
  const [selectedPlaylist, setSelectedPlaylist] = useState<PlaylistItem | null>(null);
  const [currentView, setCurrentView] = useState<'playlists' | 'tools'>('playlists');
  const [playlistLoading, setPlaylistLoading] = useState(false);
  const mcpMode = true;
  const source = tokenInfo.source ?? 'spotify';

  // Preview / apply state
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  // Current live tracks for the selected playlist — used to merge AI additions
  // The full merged suggestion list built during preview — reused by apply
  const [pendingSuggestions, setPendingSuggestions] = useState<object[]>([]);

  const { playlists, loading: playlistsLoading, fetchPlaylists, updatePlaylistCount } = usePlaylists(tokenInfo);

  const fetchTracks = useCallback(
    (id: string) => source === 'youtube' ? getYtPlaylistTracks(tokenInfo, id) : getPlaylistTracks(tokenInfo, id),
    [tokenInfo, source],
  );

  // After AI mutates a playlist: refresh list AND correct track count for the selected playlist
  const handlePlaylistMutated = useCallback(async () => {
    await fetchPlaylists();
    if (selectedPlaylist && tokenInfo) {
      try {
        const freshTracks = await fetchTracks(selectedPlaylist.id);
        updatePlaylistCount(selectedPlaylist.id, freshTracks.length);
      } catch { /* ignore */ }
    }
  }, [fetchPlaylists, selectedPlaylist, tokenInfo, updatePlaylistCount, fetchTracks]);

  const chat = useChat({
    tokenInfo,
    userId: userInfo?.id,
    playlistId: selectedPlaylist?.id,
    playlistName: selectedPlaylist?.name,
    mcpMode,
    ensureValidToken,
    onPlaylistMutated: handlePlaylistMutated,
  });

  const handleSelectPlaylist = async (p: PlaylistItem) => {
    setSelectedPlaylist(p);
    chat.clearMessages();
    setPreviewData(null);
    setApplyResult(null);

    setPlaylistLoading(true);

    try {
      // Fetch saved conversation and current tracks in parallel
      const [savedMessages, tracks] = await Promise.all([
        userInfo?.id ? loadConversation(userInfo.id, p.id) : Promise.resolve([]),
        fetchTracks(p.id),
      ]);

      updatePlaylistCount(p.id, tracks.length);

      if (savedMessages.length > 0) {
        // Restore previous conversation — tracks table is already embedded in the history
        chat.restoreMessages(savedMessages);
      } else {
        // Fresh start: inject tracks table only
        const tableContent = buildTracksTable(p, tracks, source);
        chat.clearMessages();
        chat.injectMessage(tableContent, 'user');
      }
    } catch (e) {
      console.error('Failed to load playlist:', e);
      chat.clearMessages();
      chat.injectMessage(`**${p.name}** selected. Could not load details — you can still chat about this playlist.`, 'assistant');
    } finally {
      setPlaylistLoading(false);
    }
  };

  const handleCreatePlaylist = async (name: string, description: string, isPublic: boolean) => {
    const result = await createPlaylist(tokenInfo, name, description, isPublic);
    await fetchPlaylists();
    // Auto-select the new playlist (mirrors old Streamlit behaviour)
    if (result.playlist_id) {
      const newPlaylist: PlaylistItem = {
        id: result.playlist_id,
        name,
        description,
        public: isPublic,
        tracks_total: 0,
        owner_id: userInfo?.id,
        owner_name: userInfo?.display_name ?? userInfo?.id,
      };
      await handleSelectPlaylist(newPlaylist);
    }
  };

  /**
   * Build the full final tracklist from AI suggestions.
   * Always fetches the current playlist fresh from the API to avoid stale state.
   * If the AI gave fewer tracks than currently in the playlist → treat as additions
   * and merge them in. Otherwise treat the AI output as a full replacement.
   */
  const buildMergedSuggestions = async (lastSugs: string[]): Promise<object[]> => {
    const { tracks: aiTracks } = await extractTracks(lastSugs);

    // Fetch the live playlist so we always have accurate current state
    const liveTracks = selectedPlaylist ? await fetchTracks(selectedPlaylist.id) : [];

    if (liveTracks.length === 0 || aiTracks.length >= liveTracks.length) {
      // AI gave a full replacement list (or playlist is empty)
      return aiTracks;
    }

    // AI gave additions only — keep all existing tracks, append new ones
    const aiNames = new Set(
      aiTracks.map((t: Record<string, string>) => (t.track_name ?? '').toLowerCase().trim()),
    );
    const existing = liveTracks
      .filter(t => !aiNames.has(t.name.toLowerCase().trim()))
      .map(t => ({ track_name: t.name, artist: t.artists }));
    return [...existing, ...aiTracks];
  };

  const handlePreview = async () => {
    if (!chat.lastSuggestions || !selectedPlaylist) return;
    setPreviewLoading(true);
    setApplyResult(null);
    try {
      const merged = await buildMergedSuggestions(chat.lastSuggestions);
      setPendingSuggestions(merged);
      const data = await previewChanges(tokenInfo, selectedPlaylist.id, merged);
      setPreviewData(data);
      setShowPreview(true);
    } catch (e) {
      console.error(e);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleApply = async () => {
    if (!previewData || !selectedPlaylist) return;
    setApplying(true);
    try {
      // For YouTube: reuse the already-resolved video IDs from preview to avoid
      // burning quota on a second round of search.list calls (100 units each).
      // For Spotify: re-use pendingSuggestions as before.
      const tracksToApply = source === 'youtube'
        ? previewData.tracks_to_add
        : pendingSuggestions;
      const result = await applyChanges(tokenInfo, selectedPlaylist.id, tracksToApply);
      setApplyResult(result);

      if (result.success) {
        // Fetch the now-live playlist and inject the refreshed table into chat
        const freshTracks = await fetchTracks(selectedPlaylist.id);
        updatePlaylistCount(selectedPlaylist.id, freshTracks.length);
        const tableContent = buildTracksTable(selectedPlaylist, freshTracks, source);
        chat.injectMessage(tableContent, 'user');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className={styles.layout}>
      <Sidebar
        playlists={playlists}
        selectedId={selectedPlaylist?.id ?? null}
        onSelect={handleSelectPlaylist}
        loading={playlistsLoading}
        userDisplayName={userInfo?.display_name ?? userInfo?.id}
        userId={userInfo?.id}
        onLogout={onLogout}
        onCreatePlaylist={handleCreatePlaylist}
        onRefresh={fetchPlaylists}
        currentView={currentView}
        onViewTools={() => {
          setCurrentView('tools');
          setSelectedPlaylist(null);
        }}
        onViewPlaylists={() => setCurrentView('playlists')}
      />

      <main className={styles.main}>
        {currentView === 'tools' ? (
          <ToolsPage />
        ) : selectedPlaylist ? (
          <>
            <div className={styles.playlistHeader}>
              {selectedPlaylist.images?.[0]?.url && (
                <img className={styles.playlistThumb} src={selectedPlaylist.images[0].url} alt="" />
              )}
              <div>
                <a
                  className={styles.playlistName}
                  href={
                    source === 'youtube'
                      ? `https://www.youtube.com/playlist?list=${selectedPlaylist.id}`
                      : `https://open.spotify.com/playlist/${selectedPlaylist.id}`
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {selectedPlaylist.name}
                </a>
                {selectedPlaylist.tracks_total !== undefined && (
                  <div className={styles.playlistMeta}>{selectedPlaylist.tracks_total} tracks</div>
                )}
              </div>
            </div>

            <div className={styles.chatWrap}>
              <ChatWindow
                messages={chat.messages}
                isLoading={chat.isLoading || playlistLoading}
                error={chat.error}
                onSend={chat.send}
                lastSuggestions={chat.lastSuggestions}
                onPreview={handlePreview}
                previewLoading={previewLoading}
              />
            </div>
          </>
        ) : (
          <div className={styles.welcome}>
            <div className={styles.welcomeCard}>
              <img src="/music-svgrepo-com.svg" className={styles.welcomeIcon} alt="" />
              <h1 className={styles.welcomeTitle}>Welcome to Jam-ya</h1>
              <p className={styles.welcomeSubtitle}>
                Your AI-powered {source === 'youtube' ? 'YouTube Music' : 'Spotify'} playlist manager
              </p>
              <ol className={styles.steps}>
                <li className={styles.step}>
                  <span className={styles.stepNum}>1</span>
                  <div className={styles.stepBody}>
                    <strong>Pick a playlist</strong>
                    <span>Choose one from the sidebar on the left</span>
                  </div>
                </li>
                <li className={styles.step}>
                  <span className={styles.stepNum}>2</span>
                  <div className={styles.stepBody}>
                    <strong>Tell Jam-ya what to do</strong>
                    <span>e.g. "Add 10 similar songs" or "Sort by energy"</span>
                  </div>
                </li>
                <li className={styles.step}>
                  <span className={styles.stepNum}>3</span>
                  <div className={styles.stepBody}>
                    <strong>Preview &amp; Save Changes</strong>
                    <span>Review every change before it's applied to Spotify</span>
                  </div>
                </li>
              </ol>
            </div>
          </div>
        )}
      </main>

      {showPreview && (
        <PreviewModal
          preview={previewData}
          applying={applying}
          applyResult={applyResult}
          onApply={handleApply}
          source={source as import('../types').MusicSource}
          onClose={() => {
            setShowPreview(false);
            if (applyResult) setApplyResult(null);
          }}
        />
      )}
    </div>
  );
}
