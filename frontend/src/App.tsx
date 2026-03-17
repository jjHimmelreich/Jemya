import { useAuth } from './hooks/useAuth';
import { useYouTubeAuth } from './hooks/useYouTubeAuth';
import { LoginPage } from './pages/LoginPage';
import { AppPage } from './pages/AppPage';

export default function App() {
  const spotify = useAuth();
  const youtube = useYouTubeAuth();

  const loading = spotify.loading || youtube.loading;

  // Determine active session — prefer YouTube if the URL path is a YT callback
  const activeToken = youtube.tokenInfo ?? spotify.tokenInfo;
  const activeUser = youtube.userInfo ?? spotify.userInfo;
  const activeLogout = youtube.tokenInfo ? youtube.logout : spotify.logout;
  const activeEnsureValid = youtube.tokenInfo ? youtube.ensureValidToken : spotify.ensureValidToken;

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#121212',
          color: '#3B7EA5',
          fontSize: '1.1rem',
        }}
      >
        Connecting…
      </div>
    );
  }

  if (!activeToken) {
    return <LoginPage />;
  }

  return (
    <AppPage
      tokenInfo={activeToken}
      userInfo={activeUser}
      onLogout={activeLogout}
      ensureValidToken={activeEnsureValid}
    />
  );
}

