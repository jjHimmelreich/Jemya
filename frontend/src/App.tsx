import { useAuth } from './hooks/useAuth';
import { LoginPage } from './pages/LoginPage';
import { AppPage } from './pages/AppPage';

export default function App() {
  const { tokenInfo, userInfo, loading, logout } = useAuth();

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#121212',
          color: '#1db954',
          fontSize: '1.1rem',
        }}
      >
        Connecting to Spotify…
      </div>
    );
  }

  if (!tokenInfo) {
    return <LoginPage />;
  }

  return <AppPage tokenInfo={tokenInfo} userInfo={userInfo} onLogout={logout} />;
}
