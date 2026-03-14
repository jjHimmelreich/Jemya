import type { PlaylistItem } from '../types';
import styles from './Sidebar.module.css';

interface Props {
  playlists: PlaylistItem[];
  selectedId: string | null;
  onSelect: (playlist: PlaylistItem) => void;
  loading?: boolean;
  userDisplayName?: string;
  onLogout?: () => void;
}

export function Sidebar({
  playlists,
  selectedId,
  onSelect,
  loading,
  userDisplayName,
  onLogout,
}: Props) {
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

      <div className={styles.playlistsHeader}>Your Playlists</div>

      {loading ? (
        <div className={styles.loading}>Loading playlists…</div>
      ) : (
        <ul className={styles.list}>
          {playlists.map((p) => (
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
          ))}
        </ul>
      )}
    </aside>
  );
}
