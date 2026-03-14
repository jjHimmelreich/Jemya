import { useState, useEffect, useCallback } from 'react';
import { exchangeCode, refreshToken, getMe, getLoginUrl } from '../api/client';
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

  // Handle OAuth callback code in URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (code) {
      setLoading(true);
      // Remove code from URL without reload
      window.history.replaceState({}, '', window.location.pathname);
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

  return { tokenInfo, userInfo, loading, login, logout, ensureValidToken };
}
