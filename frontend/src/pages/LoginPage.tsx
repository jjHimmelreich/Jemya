import { useState } from 'react';
import { getLoginUrl, getYtLoginUrl } from '../api/client';
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

  return (
    <div className={styles.container}>
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
    </div>
  );
}

