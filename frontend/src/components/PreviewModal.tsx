import { useState } from 'react';
import type { PreviewData, ApplyResult } from '../types';
import styles from './PreviewModal.module.css';

interface Props {
  preview: PreviewData | null;
  applying: boolean;
  applyResult: ApplyResult | null;
  onApply: () => void;
  onClose: () => void;
}

export function PreviewModal({ preview, applying, applyResult, onApply, onClose }: Props) {
  if (!preview) return null;

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h2>Preview Changes</h2>
          <button className={styles.close} onClick={onClose}>✕</button>
        </div>

        {applyResult ? (
          <div className={styles.result}>
            <div className={styles.success}>
              Applied successfully! {applyResult.added_count} track(s) added.
            </div>
            {applyResult.not_found_count > 0 && (
              <div className={styles.warn}>
                ⚠️ {applyResult.not_found_count} track(s) not found on Spotify.
              </div>
            )}
          </div>
        ) : (
          <>
            <div className={styles.summary}>
              <span className={styles.badge}>{preview.total_found} found</span>
              {preview.total_not_found > 0 && (
                <span className={`${styles.badge} ${styles.warn}`}>
                  {preview.total_not_found} not found
                </span>
              )}
            </div>

            <div className={styles.trackList}>
              {preview.tracks_to_add.map((t, i) => (
                <div key={i} className={styles.track}>
                  <span className={styles.trackName}>{t.found_name ?? t.name}</span>
                  <span className={styles.trackArtist}>{t.found_artist ?? t.artists}</span>
                </div>
              ))}
            </div>

            {preview.tracks_not_found.length > 0 && (
              <details className={styles.notFound}>
                <summary>Not found ({preview.tracks_not_found.length})</summary>
                <ul>
                  {preview.tracks_not_found.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              </details>
            )}

            <div className={styles.actions}>
              <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
              <button className={styles.applyBtn} onClick={onApply} disabled={applying}>
                {applying ? 'Applying…' : 'Apply to Spotify'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
