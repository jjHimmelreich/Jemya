// Shared TypeScript types for Jam-ya frontend

export type MusicSource = 'spotify' | 'youtube';

export interface TokenInfo {
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
  expires_at?: number;
  scope?: string;
  /** Which music service issued this token */
  source?: MusicSource;
}

export interface UserInfo {
  id: string;
  display_name?: string;
  email?: string;
  images?: Array<{ url: string; width?: number; height?: number }>;
  source?: MusicSource;
}

export interface PlaylistItem {
  id: string;
  name: string;
  description?: string;
  public?: boolean;
  images?: Array<{ url: string }>;
  tracks_total?: number;
  owner_id?: string;
  owner_name?: string;
}

export interface TrackItem {
  id?: string;
  name: string;
  artists: string;
  album?: string;
  duration_ms?: number;
  popularity?: number;
  explicit?: boolean;
  spotify_url?: string;
  uri?: string;
}

export interface PreviewTrack {
  uri: string;
  found_name?: string;
  found_artist?: string;
  found_album?: string;
  duration_ms?: number;
  spotify_url?: string;
  position_instruction?: string;
  order_index?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: number;
}

export interface PreviewData {
  tracks_to_add: PreviewTrack[];
  tracks_not_found: string[];
  total_found: number;
  total_not_found: number;
}

export interface ApplyResult {
  success: boolean;
  added_count: number;
  not_found_count: number;
  added_tracks: TrackItem[];
  not_found_tracks: string[];
  message?: string;
}
