import { useState, useMemo, useRef, useEffect } from 'react';
import type { PlaylistItem } from '../types';
import styles from './Sidebar.module.css';

interface Props {
  playlists: PlaylistItem[];
  selectedId: string | null;
  onSelect: (playlist: PlaylistItem) => void;
  loading?: boolean;
  userId?: string;
  userDisplayName?: string;
  authSource?: 'spotify' | 'youtube';
  onLogout?: () => void;
  onCreatePlaylist?: (name: string, description: string, isPublic: boolean) => Promise<void>;
  onRefresh?: () => void;
  currentView?: 'playlists' | 'tools';
  onViewTools?: () => void;
  onViewPlaylists?: () => void;
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
  authSource,
  onLogout,
  onCreatePlaylist,
  onRefresh,
  currentView,
  onViewTools,
  onViewPlaylists,
}: Props) {
  // Always start expanded so new users immediately see their playlists.
  // On mobile we auto-collapse once they select a playlist (see renderItem).
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<'recent' | 'alpha'>('recent');
  const [sortOpen, setSortOpen] = useState(false);
  const sortRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sortOpen) return;
    const handler = (e: MouseEvent) => {
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) {
        setSortOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [sortOpen]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newPublic, setNewPublic] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !onCreatePlaylist) return;
    setCreating(true);
    setCreateError(null);
    try {
      await onCreatePlaylist(newName.trim(), newDesc.trim(), newPublic);
      setNewName('');
      setNewDesc('');
      setNewPublic(false);
      setShowCreate(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create playlist');
    } finally {
      setCreating(false);
    }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    const base = q ? playlists.filter((p) => p.name.toLowerCase().includes(q)) : playlists;
    return sort === 'alpha'
      ? [...base].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
      : base;
  }, [playlists, search, sort]);

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
      onClick={() => {
        onSelect(p);
        // On mobile the sidebar overlays the screen — collapse it after selection
        // so the user can see the chat without an extra tap.
        if (window.innerWidth <= 640) setCollapsed(true);
      }}
    >
      {p.images?.[0]?.url ? (
        <img className={styles.thumb} src={p.images[0].url} alt="" />
      ) : (
        <div className={styles.thumbPlaceholder}>
          <img src="/spotify-icon.svg" alt="" className={styles.thumbPlaceholderIcon} />
        </div>
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
    <>
      {/* Mobile backdrop — closes sidebar when tapping outside */}
      {!collapsed && (
        <div className={styles.backdrop} onClick={() => setCollapsed(true)} />
      )}

      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
        <div className={styles.header}>
          <div className={styles.logoRow}>
            {!collapsed && (
              <div className={styles.logo}>
                <img src="/music-svgrepo-com.svg" alt="" className={styles.logoIcon} />
                Jam-ya
              </div>
            )}
            <button
              className={styles.toggleBtn}
              onClick={() => setCollapsed((v) => !v)}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? '›' : '‹'}
            </button>
          </div>
          {!collapsed && userDisplayName && (
            <div className={styles.user}>
              <span className={styles.userInfo}>
                {authSource === 'youtube' ? (
                  <img src="/youtube-icon.svg" alt="YouTube" className={styles.authSourceIcon} title="Connected via YouTube" />
                ) : (
                  <img src="/spotify-icon.svg" alt="Spotify" className={styles.authSourceIcon} title="Connected via Spotify" />
                )}
                {userDisplayName}
              </span>
              <button className={styles.logoutBtn} onClick={onLogout}>
                Log out
              </button>
            </div>
          )}
        </div>

        {!collapsed && (
          <div className={styles.searchBox}>
            <div className={styles.searchInputWrap}>
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
            <div className={styles.sortDropdownWrap} ref={sortRef}>
              <button
                className={`${styles.sortTrigger} ${sort === 'alpha' ? styles.sortTriggerActive : ''}`}
                onClick={() => setSortOpen((v) => !v)}
                title="Sort playlists"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M2 4h12v1.5H2zm2 3.5h8V9H4zm2 3.5h4v1.5H6z"/>
                </svg>
                <span className={styles.sortTriggerChevron}>▾</span>
              </button>
              {sortOpen && (
                <div className={styles.sortMenu}>
                  {(['recent', 'alpha'] as const).map((opt) => (
                    <button
                      key={opt}
                      className={`${styles.sortOption} ${sort === opt ? styles.sortOptionActive : ''}`}
                      onClick={() => { setSort(opt); setSortOpen(false); }}
                    >
                      {opt === 'recent' ? 'Recents' : 'Alphabetical'}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!collapsed && onCreatePlaylist && (
        <div className={styles.createSection}>
          {!showCreate ? (
            <div className={styles.createRow}>
              <button className={styles.createBtn} onClick={() => setShowCreate(true)}>
                + New Playlist
              </button>
              {onRefresh && (
                <button className={styles.refreshBtn} onClick={onRefresh} title="Reload playlists">
                  ↻
                </button>
              )}
            </div>
          ) : (
            <form className={styles.createForm} onSubmit={handleCreate}>
              <input
                className={styles.createInput}
                type="text"
                placeholder="Playlist name *"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
                required
              />
              <input
                className={styles.createInput}
                type="text"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
              <label className={styles.createCheckbox}>
                <input
                  type="checkbox"
                  checked={newPublic}
                  onChange={(e) => setNewPublic(e.target.checked)}
                />
                Make public
              </label>
              {createError && <div className={styles.createError}>{createError}</div>}
              <div className={styles.createActions}>
                <button type="submit" className={styles.createSubmit} disabled={creating || !newName.trim()}>
                  {creating ? 'Creating…' : 'Create'}
                </button>
                <button type="button" className={styles.createCancel} onClick={() => { setShowCreate(false); setCreateError(null); }}>
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
        )}

        {loading && !collapsed ? (
          <div className={styles.loading}>Loading playlists…</div>
        ) : !collapsed ? (
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
        ) : null}

        <nav className={styles.bottomNav}>
          <button
            className={`${styles.bottomNavBtn} ${currentView !== 'tools' ? styles.bottomNavActive : ''}`}
            onClick={onViewPlaylists}
            title="Playlists"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z"/></svg>
            {!collapsed && <span>Playlists</span>}
          </button>
          <button
            className={`${styles.bottomNavBtn} ${currentView === 'tools' ? styles.bottomNavActive : ''}`}
            onClick={onViewTools}
            title="Tools"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/></svg>
            {!collapsed && <span>Tools</span>}
          </button>
        </nav>
      </aside>
    </>
  );
}
