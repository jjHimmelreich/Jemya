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

function CollapsibleGroup({
  title,
  count,
  children,
  defaultOpen = true,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button className={styles.groupHeader} onClick={() => setOpen((v) => !v)}>
        <span className={styles.groupChevron}>{open ? '▾' : '▸'}</span>
        <span className={styles.groupTitle}>{title}</span>
        <span className={styles.groupCount}>{count}</span>
      </button>
      {open && children}
    </div>
  );
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

  // Group others by owner
  const byOwner = useMemo(() => {
    const map = new Map<string, { name: string; playlists: PlaylistItem[] }>();
    for (const p of filtered) {
      if (p.owner_id === userId) continue;
      const key = p.owner_id ?? 'unknown';
      if (!map.has(key)) {
        map.set(key, { name: p.owner_name ?? p.owner_id ?? 'Unknown', playlists: [] });
      }
      map.get(key)!.playlists.push(p);
    }
    return Array.from(map.entries()).sort((a, b) =>
      a[1].name.localeCompare(b[1].name),
    );
  }, [filtered, userId]);

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
            <CollapsibleGroup title="My Playlists" count={myPlaylists.length} defaultOpen={true}>
              <ul className={styles.list}>{myPlaylists.map(renderItem)}</ul>
            </CollapsibleGroup>
          )}

          {byOwner.map(([ownerId, { name, playlists: ownerPlaylists }]) => (
            <CollapsibleGroup
              key={ownerId}
              title={name}
              count={ownerPlaylists.length}
              defaultOpen={false}
            >
              <ul className={styles.list}>{ownerPlaylists.map(renderItem)}</ul>
            </CollapsibleGroup>
          ))}

          {filtered.length === 0 && (
            <div className={styles.noResults}>No playlists match "{search}"</div>
          )}
        </div>
      )}
    </aside>
  );
}
