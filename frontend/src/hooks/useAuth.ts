import { useState, useEffect, useCallback } from 'react';
import { exchangeCode, refreshToken, getMe, getLoginUrl, setSessionExpiredHandler } from '../api/client';
import type { TokenInfo, UserInfo } from '../types';

const TOKEN_KEY = 'jemya_token';

export function useAuth() {
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    return stored ? JSON.parse(stored) : null;
  });
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(false);

  // Persist token changes
  useEffect(() => {
    if (tokenInfo) {
      localStorage.setItem(TOKEN_KEY, JSON.stringify(tokenInfo));
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }, [tokenInfo]);

  // Load user info when token is available
  useEffect(() => {
    if (tokenInfo && !userInfo) {
      getMe(tokenInfo)
        .then(setUserInfo)
        .catch(() => logout());
    }
  }, [tokenInfo]);

  // Handle Spotify OAuth callback: http://127.0.0.1:5555/callback?code=...
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (code) {
      setLoading(true);
      // Redirect back to root after consuming the code
      window.history.replaceState({}, '', '/');
      exchangeCode(code)
        .then((token) => setTokenInfo(token))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, []);

  const login = useCallback(async () => {
    const url = await getLoginUrl();
    window.location.href = url;
  }, []);

  const logout = useCallback(() => {
    setTokenInfo(null);
    setUserInfo(null);
  }, []);

  // Wire 401 interceptor: expired token → clean logout
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setTokenInfo(null);
      setUserInfo(null);
    });
  }, []);

  const ensureValidToken = useCallback(async (): Promise<TokenInfo | null> => {
    if (!tokenInfo) return null;
    const now = Date.now() / 1000;
    if (tokenInfo.expires_at && tokenInfo.expires_at - now < 60) {
      try {
        const refreshed = await refreshToken(tokenInfo);
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
          const refreshed = await refreshToken(tokenInfo);
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
