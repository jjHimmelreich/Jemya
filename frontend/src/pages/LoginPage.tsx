import { useState } from 'react';
import { getLoginUrl } from '../api/client';
import styles from './LoginPage.module.css';

export function LoginPage() {
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    const url = await getLoginUrl();
    window.location.href = url;
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <img src="/music-svgrepo-com.svg" alt="Jemya" className={styles.logoImg} />
        </div>
        <h1 className={styles.title}>Jemya</h1>
        <p className={styles.subtitle}>Your AI-powered playlist companion</p>
        <button className={styles.loginBtn} onClick={handleLogin} disabled={loading}>
          {loading ? 'Redirecting…' : 'Connect with Spotify'}
        </button>
        <p className={styles.hint}>
          Jemya enriches and transforms your playlists using AI. Connect your Spotify account to get
          started.
        </p>
      </div>
    </div>
  );
}
