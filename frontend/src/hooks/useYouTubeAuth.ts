import { useState, useEffect, useCallback } from 'react';
import { exchangeYtCode, refreshYtToken, getYtMe, getYtLoginUrl } from '../api/client';
import type { TokenInfo, UserInfo } from '../types';

const YT_TOKEN_KEY = 'yt_token';

export function useYouTubeAuth() {
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(() => {
    const stored = localStorage.getItem(YT_TOKEN_KEY);
    return stored ? JSON.parse(stored) : null;
  });
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(false);

  // Persist token changes
  useEffect(() => {
    if (tokenInfo) {
      localStorage.setItem(YT_TOKEN_KEY, JSON.stringify(tokenInfo));
    } else {
      localStorage.removeItem(YT_TOKEN_KEY);
    }
  }, [tokenInfo]);

  // Load user info when token is available
  useEffect(() => {
    if (tokenInfo && !userInfo) {
      getYtMe(tokenInfo)
        .then(setUserInfo)
        .catch(() => logout());
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenInfo]);

  // Handle YouTube OAuth callback: http://localhost:5555/callback/youtube?code=...
  // Google OAuth sends the code via the regular ?code= parameter on the redirect URI.
  // We only process it when the current path is /callback/youtube.
  useEffect(() => {
    if (!window.location.pathname.startsWith('/callback/youtube')) return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (code) {
      setLoading(true);
      window.history.replaceState({}, '', '/');
      exchangeYtCode(code)
        .then((token) => setTokenInfo(token))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, []);

  const login = useCallback(async () => {
    const url = await getYtLoginUrl();
    window.location.href = url;
  }, []);

  const logout = useCallback(() => {
    setTokenInfo(null);
    setUserInfo(null);
  }, []);

  const ensureValidToken = useCallback(async (): Promise<TokenInfo | null> => {
    if (!tokenInfo) return null;
    const now = Date.now() / 1000;
    if (tokenInfo.expires_at && tokenInfo.expires_at - now < 60) {
      try {
        const refreshed = await refreshYtToken(tokenInfo);
        setTokenInfo(refreshed);
        return refreshed;
      } catch {
        logout();
        return null;
      }
    }
    return tokenInfo;
  }, [tokenInfo, logout]);

  // Proactive background refresh: check every 30s, refresh if within 2 minutes of expiry
  useEffect(() => {
    if (!tokenInfo) return;
    const interval = setInterval(async () => {
      const now = Date.now() / 1000;
      if (tokenInfo.expires_at && tokenInfo.expires_at - now < 120) {
        try {
          const refreshed = await refreshYtToken(tokenInfo);
          setTokenInfo(refreshed);
        } catch {
          logout();
        }
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, [tokenInfo, logout]);

  return { tokenInfo, userInfo, loading, login, logout, ensureValidToken };
}
