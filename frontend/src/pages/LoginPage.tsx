import { useState } from 'react';
import { getLoginUrl, getYtLoginUrl } from '../api/client';
import { TOOLS } from '../data/tools';
import styles from './LoginPage.module.css';

export function LoginPage() {
  const [loadingSpotify, setLoadingSpotify] = useState(false);
  const [loadingYt, setLoadingYt] = useState(false);

  const handleSpotifyLogin = async () => {
    setLoadingSpotify(true);
    const url = await getLoginUrl();
    window.location.href = url;
  };

  const handleYouTubeLogin = async () => {
    setLoadingYt(true);
    const url = await getYtLoginUrl();
    window.location.href = url;
  };

  const availableTools = TOOLS.filter((t) => t.status !== 'coming-soon');

  return (
    <div className={styles.page}>
      {/* ── Hero / Login section ───────────────────────────────────── */}
      <section className={styles.hero}>
        <div className={styles.card}>
          <div className={styles.logo}>
            <img src="/music-svgrepo-com.svg" alt="Jam-ya" className={styles.logoImg} />
          </div>
          <h1 className={styles.title}>Jam-ya</h1>
          <p className={styles.subtitle}>Your AI-powered playlist companion</p>

          <button
            className={styles.loginBtn}
            onClick={handleSpotifyLogin}
            disabled={loadingSpotify || loadingYt}
          >
            {loadingSpotify ? 'Redirecting…' : 'Connect to Spotify'}
          </button>

          <button
            className={`${styles.loginBtn} ${styles.loginBtnYt}`}
            onClick={handleYouTubeLogin}
            disabled={loadingSpotify || loadingYt}
          >
            {loadingYt ? 'Redirecting…' : 'Connect to YouTube'}
          </button>

          <p className={styles.hint}>
            Jam-ya enriches and transforms your playlists using AI. Connect your Spotify or YouTube
            account to get started.
          </p>
        </div>
      </section>

      {/* ── Tools section ─────────────────────────────────────────── */}
      <section className={styles.toolsSection}>
        <div className={styles.toolsSectionHeader}>
          <h2 className={styles.toolsSectionTitle}>🔧 Jemya Toolkit</h2>
          <p className={styles.toolsSectionSubtitle}>
            Free tools you can use right now — no login required
          </p>
        </div>

        <div className={styles.toolsGrid}>
          {availableTools.map((tool) => (
            <div key={tool.id} className={styles.toolCard}>
              <span className={styles.toolIcon}>{tool.icon}</span>
              <div className={styles.toolInfo}>
                <h3 className={styles.toolName}>{tool.name}</h3>
                <p className={styles.toolDescription}>{tool.description}</p>
              </div>
              {tool.url && (
                <a
                  href={tool.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.toolLink}
                >
                  View on GitHub →
                </a>
              )}
            </div>
          ))}
        </div>

        {/* CTA banner */}
        <div className={styles.ctaBanner}>
          <p className={styles.ctaText}>
            🎵 <strong>Want AI-powered playlist generation, analysis and more?</strong>
          </p>
          <div className={styles.ctaButtons}>
            <button
              className={styles.ctaBtn}
              onClick={handleSpotifyLogin}
              disabled={loadingSpotify || loadingYt}
            >
              {loadingSpotify ? 'Redirecting…' : 'Login with Spotify'}
            </button>
            <button
              className={`${styles.ctaBtn} ${styles.ctaBtnYt}`}
              onClick={handleYouTubeLogin}
              disabled={loadingSpotify || loadingYt}
            >
              {loadingYt ? 'Redirecting…' : 'Login with YouTube'}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

