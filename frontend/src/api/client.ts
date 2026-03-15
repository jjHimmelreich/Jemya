import axios from 'axios';
import type { TokenInfo, PlaylistItem, TrackItem, PreviewData, ApplyResult, UserInfo } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

const http = axios.create({ baseURL: BASE_URL });

// Called by useAuth to wire up session-expiry handling.
// When the backend returns 401, we call onSessionExpired so the user gets
// logged out cleanly rather than seeing a silent API failure.
let _onSessionExpired: (() => void) | null = null;
export const setSessionExpiredHandler = (handler: () => void) => {
  _onSessionExpired = handler;
};

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && _onSessionExpired) {
      _onSessionExpired();
    }
    return Promise.reject(err);
  },
);

// ── Auth ──────────────────────────────────────────────────────────────────────

export const getLoginUrl = async (): Promise<string> => {
  const { data } = await http.get<{ auth_url: string }>('/auth/login-url');
  return data.auth_url;
};

export const exchangeCode = async (code: string): Promise<TokenInfo> => {
  const { data } = await http.post<{ token_info: TokenInfo }>('/auth/callback', { code });
  return data.token_info;
};

export const refreshToken = async (tokenInfo: TokenInfo): Promise<TokenInfo> => {
  const { data } = await http.post<{ token_info: TokenInfo }>('/auth/refresh', {
    token_info: tokenInfo,
  });
  return data.token_info;
};

export const getMe = async (tokenInfo: TokenInfo): Promise<UserInfo> => {
  const { data } = await http.post<UserInfo>('/auth/me', { token_info: tokenInfo });
  return data;
};

// ── Playlists ─────────────────────────────────────────────────────────────────

export const getPlaylists = async (tokenInfo: TokenInfo): Promise<PlaylistItem[]> => {
  const { data } = await http.post<PlaylistItem[]>('/playlists/', {
    token_info: tokenInfo,
  });
  return data;
};

export const getPlaylistTracks = async (
  tokenInfo: TokenInfo,
  playlistId: string,
): Promise<TrackItem[]> => {
  const { data } = await http.post<TrackItem[]>(`/playlists/${playlistId}/tracks`, {
    token_info: tokenInfo,
  });
  return data;
};

export const createPlaylist = async (
  tokenInfo: TokenInfo,
  name: string,
  description = '',
  isPublic = false,
): Promise<{ success: boolean; playlist_id: string; message: string }> => {
  const { data } = await http.post(`/playlists/create`, {
    token_info: tokenInfo,
    name,
    description,
    public: isPublic,
  });
  return data;
};

export const previewChanges = async (
  tokenInfo: TokenInfo,
  playlistId: string,
  trackSuggestions: object[],
): Promise<PreviewData> => {
  const { data } = await http.post<PreviewData>(`/playlists/${playlistId}/preview`, {
    token_info: tokenInfo,
    playlist_id: playlistId,
    track_suggestions: trackSuggestions,
  });
  return data;
};

export const applyChanges = async (
  tokenInfo: TokenInfo,
  playlistId: string,
  trackSuggestions: object[],
): Promise<ApplyResult> => {
  const { data } = await http.post<ApplyResult>(`/playlists/${playlistId}/apply`, {
    token_info: tokenInfo,
    playlist_id: playlistId,
    track_suggestions: trackSuggestions,
  });
  return data;
};

// ── AI ────────────────────────────────────────────────────────────────────────

export interface ChatApiResponse {
  response: string;
  track_suggestions?: string[];
  tool_calls?: { name: string; arguments: string }[];
}

export const sendChat = async (params: {
  tokenInfo: TokenInfo;
  userMessage: string;
  conversationHistory: object[];
  playlistId?: string;
  playlistName?: string;
  userId?: string;
  mcpMode?: boolean;
}): Promise<ChatApiResponse> => {
  const endpoint = params.mcpMode ? '/mcp/chat' : '/ai/chat';
  const { data } = await http.post<ChatApiResponse>(endpoint, {
    token_info: params.tokenInfo,
    user_message: params.userMessage,
    conversation_history: params.conversationHistory,
    playlist_id: params.playlistId,
    playlist_name: params.playlistName,
    user_id: params.userId,
    mcp_mode: params.mcpMode ?? false,
  });
  return data;
};

export const loadConversation = async (
  userId: string,
  playlistId: string,
): Promise<{ role: string; content: string }[]> => {
  const { data } = await http.post<{ messages: { role: string; content: string }[] }>(
    '/ai/load-conversation',
    { user_id: userId, playlist_id: playlistId },
  );
  return data.messages ?? [];
};

export const extractTracks = async (
  trackSuggestions: string[],
): Promise<{ tracks: object[] }> => {
  const { data } = await http.post('/ai/extract-tracks', {
    track_suggestions: trackSuggestions,
  });
  return data;
};
