import { useState } from 'react';
import { Sidebar } from '../components/Sidebar';
import { ChatWindow } from '../components/ChatWindow';
import { PreviewModal } from '../components/PreviewModal';
import { useChat } from '../hooks/useChat';
import { usePlaylists } from '../hooks/usePlaylists';
import { extractTracks, previewChanges, applyChanges } from '../api/client';
import type { PlaylistItem, TokenInfo, UserInfo, PreviewData, ApplyResult } from '../types';
import styles from './AppPage.module.css';

interface Props {
  tokenInfo: TokenInfo;
  userInfo: UserInfo | null;
  onLogout: () => void;
}

export function AppPage({ tokenInfo, userInfo, onLogout }: Props) {
  const [selectedPlaylist, setSelectedPlaylist] = useState<PlaylistItem | null>(null);
  const mcpMode = true;

  // Preview / apply state
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);

  const { playlists, loading: playlistsLoading } = usePlaylists(tokenInfo);

  const chat = useChat({
    tokenInfo,
    userId: userInfo?.id,
    playlistId: selectedPlaylist?.id,
    playlistName: selectedPlaylist?.name,
    mcpMode,
  });

  const handleSelectPlaylist = (p: PlaylistItem) => {
    setSelectedPlaylist(p);
    chat.clearMessages();
    setPreviewData(null);
    setApplyResult(null);
  };

  const handlePreview = async () => {
    if (!chat.lastSuggestions || !selectedPlaylist) return;
    setPreviewLoading(true);
    setApplyResult(null);
    try {
      const { tracks } = await extractTracks(chat.lastSuggestions);
      const data = await previewChanges(tokenInfo, selectedPlaylist.id, tracks);
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
      const { tracks } = await extractTracks(chat.lastSuggestions ?? []);
      const result = await applyChanges(tokenInfo, selectedPlaylist.id, tracks);
      setApplyResult(result);
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
        onLogout={onLogout}
      />

      <main className={styles.main}>
        {selectedPlaylist ? (
          <>
            <div className={styles.playlistHeader}>
              {selectedPlaylist.images?.[0]?.url && (
                <img className={styles.playlistThumb} src={selectedPlaylist.images[0].url} alt="" />
              )}
              <div>
                <div className={styles.playlistName}>{selectedPlaylist.name}</div>
                {selectedPlaylist.tracks_total !== undefined && (
                  <div className={styles.playlistMeta}>{selectedPlaylist.tracks_total} tracks</div>
                )}
              </div>
            </div>

            <ChatWindow
              messages={chat.messages}
              isLoading={chat.isLoading}
              error={chat.error}
              onSend={chat.send}
              lastSuggestions={chat.lastSuggestions}
              onPreview={handlePreview}
              onApply={() => {
                handlePreview();
              }}
            />
          </>
        ) : (
          <div className={styles.noSelection}>
            <span>👈 Select a playlist to get started</span>
          </div>
        )}
      </main>

      {showPreview && (
        <PreviewModal
          preview={previewData}
          applying={applying}
          applyResult={applyResult}
          onApply={handleApply}
          onClose={() => {
            setShowPreview(false);
            if (applyResult) setApplyResult(null);
          }}
        />
      )}
    </div>
  );
}
