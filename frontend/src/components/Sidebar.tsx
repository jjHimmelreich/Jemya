import { useState, useMemo } from 'react';
import type { PlaylistItem } from '../types';
import styles from './Sidebar.module.css';

interface Props {
  playlists: PlaylistItem[];
  selectedId: string | null;
  onSelect: (playlist: PlaylistItem) => void;
  loading?: boolean;
  userId?: string;
  userDisplayName?: string;
  onLogout?: () => void;
}

export function Sidebar({
  playlists,
  selectedId,
  onSelect,
  loading,
  userId,
  userDisplayName,
  onLogout,
}: Props) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return q ? playlists.filter((p) => p.name.toLowerCase().includes(q)) : playlists;
  }, [playlists, search]);

  const myPlaylists = filtered.filter((p) => p.owner_id === userId);
  const otherPlaylists = filtered.filter((p) => p.owner_id !== userId);

  const renderItem = (p: PlaylistItem) => (
    <li
      key={p.id}
      className={`${styles.item} ${p.id === selectedId ? styles.active : ''}`}
      onClick={() => onSelect(p)}
    >
      {p.images?.[0]?.url ? (
        <img className={styles.thumb} src={p.images[0].url} alt="" />
      ) : (
        <div className={styles.thumbPlaceholder}>🎵</div>
      )}
      <div className={styles.meta}>
        <span className={styles.name}>{p.name}</span>
        {p.tracks_total !== undefined && (
          <span className={styles.count}>{p.tracks_total} tracks</span>
        )}
      </div>
    </li>
  );

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <div className={styles.logo}>🎵 Jemya</div>
        {userDisplayName && (
          <div className={styles.user}>
            <span>{userDisplayName}</span>
            <button className={styles.logoutBtn} onClick={onLogout}>
              Log out
            </button>
          </div>
        )}
      </div>

      <div className={styles.searchBox}>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="Search playlists…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button className={styles.clearBtn} onClick={() => setSearch('')}>✕</button>
        )}
      </div>

      {loading ? (
        <div className={styles.loading}>Loading playlists…</div>
      ) : (
        <div className={styles.listContainer}>
          {myPlaylists.length > 0 && (
            <>
              <div className={styles.groupHeader}>My Playlists</div>
              <ul className={styles.list}>{myPlaylists.map(renderItem)}</ul>
            </>
          )}
          {otherPlaylists.length > 0 && (
            <>
              <div className={styles.groupHeader}>Followed & Collaborative</div>
              <ul className={styles.list}>{otherPlaylists.map(renderItem)}</ul>
            </>
          )}
          {filtered.length === 0 && (
            <div className={styles.noResults}>No playlists match "{search}"</div>
          )}
        </div>
      )}
    </aside>
  );
}
