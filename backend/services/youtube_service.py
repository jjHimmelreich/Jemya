"""
YouTube OAuth Service
Handles Google OAuth 2.0 flow for YouTube Data API v3 access.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import configuration_manager as conf

# Cache directory — relative to the repo root, next to the backend package
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache" / "yt_search"
_PLAYLISTS_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache" / "yt_playlists"
_TRACKS_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache" / "yt_tracks"
_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_PLAYLISTS_CACHE_TTL_SECONDS = 24 * 3600  # 1 day
_TRACKS_CACHE_TTL_SECONDS = 10 * 60  # 10 minutes

_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"


class YouTubeService:
    """Stateless YouTube API service – all state is passed in, nothing stored internally."""

    def __init__(self):
        self.client_id = conf.YOUTUBE_CLIENT_ID
        self.client_secret = conf.YOUTUBE_CLIENT_SECRET
        self.redirect_uri = conf.YOUTUBE_REDIRECT_URI

    def _build_flow(self) -> Flow:
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uris": [self.redirect_uri],
                "auth_uri": _AUTH_URI,
                "token_uri": _TOKEN_URI,
            }
        }
        flow = Flow.from_client_config(client_config, scopes=_SCOPES)
        flow.redirect_uri = self.redirect_uri
        return flow

    def get_auth_url(self) -> str:
        """Return the Google OAuth authorization URL (no PKCE — stateless server flow)."""
        import urllib.parse
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{_AUTH_URI}?{urllib.parse.urlencode(params)}"

    def get_token_from_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access + refresh token.

        Uses a direct POST to avoid google_auth_oauthlib's stateful Flow (which
        generates a CSRF state during authorization_url() and validates it during
        fetch_token() — impossible in a stateless REST backend).
        """
        resp = requests.post(
            _TOKEN_URI,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if not resp.ok:
            raise ValueError(f"Google token exchange failed: {resp.status_code} {resp.text}")
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Google token error: {data['error']} – {data.get('error_description', '')}")
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "token_type": "Bearer",
            "expires_in": data.get("expires_in", 3600),
            "expires_at": time.time() + data.get("expires_in", 3600),
            "scope": data.get("scope", " ".join(_SCOPES)),
            "source": "youtube",
        }

    def refresh_token_if_needed(self, token_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a refreshed token_info if within 60 s of expiry, else return as-is."""
        if not token_info or not isinstance(token_info, dict):
            return None
        expires_at = token_info.get("expires_at")
        if expires_at and time.time() > float(expires_at) - 60:
            refresh_token = token_info.get("refresh_token")
            if not refresh_token:
                return None
            try:
                resp = requests.post(
                    _TOKEN_URI,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                new_info = dict(token_info)
                new_info["access_token"] = data["access_token"]
                new_info["expires_in"] = data.get("expires_in", 3600)
                new_info["expires_at"] = time.time() + data.get("expires_in", 3600)
                # Google sometimes omits refresh_token in the response — keep the old one
                if "refresh_token" in data:
                    new_info["refresh_token"] = data["refresh_token"]
                return new_info
            except Exception as e:
                print(f"ERROR: YouTube token refresh failed: {e}")
                return None
        return token_info

    def get_user_info(self, token_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return profile info for the authenticated Google user.

        Uses the OAuth2 userinfo endpoint rather than the YouTube channels API
        so it works even when the Google account has no YouTube channel.
        """
        try:
            access_token = token_info.get("access_token")
            resp = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "id": data.get("sub"),
                "display_name": data.get("name") or data.get("email", "YouTube User"),
                "images": [{"url": data["picture"]}] if data.get("picture") else [],
                "source": "youtube",
            }
        except Exception as e:
            print(f"Error getting YouTube user info: {e}")
            return None

    # Built-in YouTube playlist IDs available to every authenticated Google account
    _BUILTIN_PLAYLISTS = [
        {"id": "LL",  "name": "Liked Videos",  "description": "Videos you have liked"},
        {"id": "WL",  "name": "Watch Later",   "description": "Videos saved to watch later"},
    ]

    @staticmethod
    def _playlists_cache_key(token_info: Dict[str, Any]) -> str:
        # Use refresh_token as stable user identifier (doesn't change on token refresh).
        # Fall back to access_token if no refresh_token present.
        stable = token_info.get("refresh_token") or token_info.get("access_token", "")
        return hashlib.md5(stable.encode()).hexdigest()

    @staticmethod
    def _playlists_cache_get(key: str) -> Optional[List[Dict[str, Any]]]:
        path = _PLAYLISTS_CACHE_DIR / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("_cached_at", 0) > _PLAYLISTS_CACHE_TTL_SECONDS:
                path.unlink(missing_ok=True)
                return None
            print(f"YouTube playlists cache HIT for key {key[:8]}…")
            return data["playlists"]
        except Exception:
            return None

    @staticmethod
    def _playlists_cache_set(key: str, playlists: List[Dict[str, Any]]) -> None:
        try:
            _PLAYLISTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _PLAYLISTS_CACHE_DIR / f"{key}.json"
            path.write_text(json.dumps({"_cached_at": time.time(), "playlists": playlists}))
        except Exception as e:
            print(f"WARNING: YouTube playlists cache write failed: {e}")

    def get_user_playlists(self, token_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return all playlists owned by the authenticated user.

        Falls back to built-in playlists (Liked Videos, Watch Later) when the
        Google account has no YouTube channel (channelNotFound).
        Caches the result per user for 24 hours.
        """
        cache_key = self._playlists_cache_key(token_info)
        cached = self._playlists_cache_get(cache_key)
        if cached is not None:
            return cached

        print(f"YouTube playlists cache MISS for key {cache_key[:8]}… — calling playlists.list")
        yt = self._client(token_info)
        playlists: List[Dict[str, Any]] = []

        # ── channel playlists ───────────────────────────────────────────────
        try:
            page_token = None
            while True:
                kwargs: Dict[str, Any] = dict(part="snippet,contentDetails,status", mine=True, maxResults=50)
                if page_token:
                    kwargs["pageToken"] = page_token
                resp = yt.playlists().list(**kwargs).execute()
                for p in resp.get("items", []):
                    snippet = p.get("snippet", {})
                    thumbs = snippet.get("thumbnails", {})
                    thumb_url = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
                    playlists.append({
                        "id": p["id"],
                        "name": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "public": p.get("status", {}).get("privacyStatus") == "public",
                        "images": [{"url": thumb_url}] if thumb_url else [],
                        "tracks_total": p["contentDetails"]["itemCount"],
                        "owner_id": snippet.get("channelId", ""),
                        "owner_name": snippet.get("channelTitle", ""),
                    })
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            if "channelNotFound" not in str(e):
                print(f"Error in get_user_playlists (YouTube): {e}")
            # No YouTube channel — fall through to built-in playlists below

        # ── built-in playlists (always available) ───────────────────────────
        existing_ids = {p["id"] for p in playlists}
        for bp in self._BUILTIN_PLAYLISTS:
            if bp["id"] not in existing_ids:
                # Verify the playlist is accessible before advertising it
                try:
                    resp = yt.playlistItems().list(
                        part="id", playlistId=bp["id"], maxResults=1
                    ).execute()
                    # Only include if the API returns without error
                    playlists.append({
                        "id": bp["id"],
                        "name": bp["name"],
                        "description": bp["description"],
                        "public": False,
                        "images": [],
                        "tracks_total": len(resp.get("items", [])),
                        "owner_id": "",
                        "owner_name": "",
                    })
                except Exception:
                    pass  # skip built-in playlists we can't access

        self._playlists_cache_set(cache_key, playlists)
        return playlists

    def create_playlist(
        self, token_info: Dict[str, Any], name: str, description: str = "", public: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """Create a new YouTube playlist and return (success, message, playlist_id)."""
        try:
            yt = self._client(token_info)
            privacy = "public" if public else "private"
            body = {
                "snippet": {"title": name, "description": description},
                "status": {"privacyStatus": privacy},
            }
            resp = yt.playlists().insert(part="snippet,status", body=body).execute()
            playlist_id = resp["id"]
            snippet = resp.get("snippet", {})
            thumbs = snippet.get("thumbnails", {})
            thumb_url = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")

            # Append to the cached playlists list so next fetch is free
            cache_key = self._playlists_cache_key(token_info)
            cached = self._playlists_cache_get(cache_key)
            if cached is not None:
                cached.append({
                    "id": playlist_id,
                    "name": name,
                    "description": description,
                    "public": public,
                    "images": [{"url": thumb_url}] if thumb_url else [],
                    "tracks_total": 0,
                    "owner_id": snippet.get("channelId", ""),
                    "owner_name": snippet.get("channelTitle", ""),
                })
                self._playlists_cache_set(cache_key, cached)

            return True, f"Playlist '{name}' created successfully!", playlist_id
        except Exception as e:
            return False, f"Failed to create YouTube playlist: {e}", None

    @staticmethod
    def _tracks_cache_get(playlist_id: str) -> Optional[List[Dict[str, Any]]]:
        path = _TRACKS_CACHE_DIR / f"{playlist_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("_cached_at", 0) > _TRACKS_CACHE_TTL_SECONDS:
                path.unlink(missing_ok=True)
                return None
            print(f"YouTube tracks cache HIT: playlist {playlist_id}")
            return data["tracks"]
        except Exception:
            return None

    @staticmethod
    def _tracks_cache_set(playlist_id: str, tracks: List[Dict[str, Any]]) -> None:
        try:
            _TRACKS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _TRACKS_CACHE_DIR / f"{playlist_id}.json"
            path.write_text(json.dumps({"_cached_at": time.time(), "tracks": tracks}))
        except Exception as e:
            print(f"WARNING: YouTube tracks cache write failed: {e}")

    @staticmethod
    def _tracks_cache_invalidate(playlist_id: str) -> None:
        path = _TRACKS_CACHE_DIR / f"{playlist_id}.json"
        path.unlink(missing_ok=True)

    def get_playlist_tracks(self, token_info: Dict[str, Any], playlist_id: str) -> List[Dict[str, Any]]:
        """Return all videos in a YouTube playlist, including real durations."""
        cached = self._tracks_cache_get(playlist_id)
        if cached is not None:
            return cached

        print(f"YouTube tracks cache MISS: playlist {playlist_id} — calling playlistItems.list")
        try:
            yt = self._client(token_info)
            tracks = []
            page_token = None
            while True:
                kwargs: Dict[str, Any] = dict(
                    part="snippet,contentDetails", playlistId=playlist_id, maxResults=50
                )
                if page_token:
                    kwargs["pageToken"] = page_token
                resp = yt.playlistItems().list(**kwargs).execute()
                for item in resp.get("items", []):
                    snippet = item.get("snippet", {})
                    resource = snippet.get("resourceId", {})
                    if resource.get("kind") != "youtube#video":
                        continue
                    video_id = resource.get("videoId", "")
                    tracks.append({
                        "id": video_id,
                        "name": snippet.get("title", "Unknown"),
                        "artists": snippet.get("videoOwnerChannelTitle", ""),
                        "album": "",
                        "duration_ms": 0,
                        "uri": video_id,
                        "spotify_url": f"https://www.youtube.com/watch?v={video_id}",
                    })
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

            # Fetch real durations in batches of 50
            if tracks:
                video_ids = [t["id"] for t in tracks]
                duration_map: Dict[str, int] = {}
                for i in range(0, len(video_ids), 50):
                    batch = video_ids[i:i + 50]
                    vid_resp = yt.videos().list(
                        part="contentDetails", id=",".join(batch)
                    ).execute()
                    for v in vid_resp.get("items", []):
                        iso = v.get("contentDetails", {}).get("duration", "PT0S")
                        duration_map[v["id"]] = self._iso8601_to_ms(iso)
                for t in tracks:
                    t["duration_ms"] = duration_map.get(t["id"], 0)

            self._tracks_cache_set(playlist_id, tracks)
            return tracks
        except Exception as e:
            print(f"Error in get_playlist_tracks (YouTube): {e}")
            return []

    @staticmethod
    def _iso8601_to_ms(duration: str) -> int:
        """Convert ISO 8601 duration (e.g. PT1H3M45S) to milliseconds."""
        import re as _re
        m = _re.match(r'PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?', duration)
        if not m:
            return 0
        h = int(m.group('h') or 0)
        mins = int(m.group('m') or 0)
        s = int(m.group('s') or 0)
        return (h * 3600 + mins * 60 + s) * 1000

    # ── Track Search / Preview ────────────────────────────────────────────────

    @staticmethod
    def _cache_key(query: str) -> str:
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    @staticmethod
    def _cache_get(key: str) -> Optional[Dict[str, Any]]:
        path = _CACHE_DIR / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("_cached_at", 0) > _CACHE_TTL_SECONDS:
                path.unlink(missing_ok=True)
                return None
            return data.get("result")
        except Exception:
            return None

    @staticmethod
    def _cache_set(key: str, result: Optional[Dict[str, Any]]) -> None:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _CACHE_DIR / f"{key}.json"
            path.write_text(json.dumps({"_cached_at": time.time(), "result": result}))
        except Exception as e:
            print(f"WARNING: YouTube cache write failed: {e}")

    def search_video(self, yt, track_name: str, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search YouTube for a video matching track_name + artist_name.
        Results are cached on disk for 7 days to preserve quota.
        """
        query = f"{track_name} {artist_name}".strip()
        key = self._cache_key(query)

        cached = self._cache_get(key)
        if cached is not None:
            print(f"YouTube cache HIT: '{query}'")
            return cached
        if cached is None and (_CACHE_DIR / f"{key}.json").exists():
            # Explicit None stored means a previous search returned no result
            print(f"YouTube cache HIT (no result): '{query}'")
            return None

        print(f"YouTube cache MISS: '{query}' — calling search.list (100 quota units)")
        try:
            resp = yt.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=1,
                videoCategoryId="10",  # Music category
            ).execute()
            items = resp.get("items", [])
            if not items:
                # Retry without music category filter
                resp = yt.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    maxResults=1,
                ).execute()
                items = resp.get("items", [])
            if items:
                item = items[0]
                video_id = item["id"]["videoId"]
                snippet = item.get("snippet", {})
                result = {
                    "uri": video_id,
                    "found_name": snippet.get("title", track_name),
                    "found_artist": snippet.get("channelTitle", artist_name),
                    "found_album": "",
                    "duration_ms": 0,
                    "spotify_url": f"https://www.youtube.com/watch?v={video_id}",
                    "position_instruction": "at the end",
                    "order_index": 0,
                }
                self._cache_set(key, result)
                return result
            else:
                self._cache_set(key, None)  # cache the miss too
                return None
        except Exception as e:
            print(f"YouTube search error for '{query}': {e}")
            return None

    def preview_changes(
        self, token_info: Dict[str, Any], playlist_id: str, track_suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Return a preview of what YouTube videos would be added, without modifying the playlist."""
        yt = self._client(token_info)
        found, not_found = [], []
        for td in track_suggestions:
            if not isinstance(td, dict):
                continue
            name = td.get("track_name", "").strip()
            artist = td.get("artist", "").strip()
            if not name:
                continue
            result = self.search_video(yt, name, artist)
            if result:
                result["position_instruction"] = td.get("position_instruction", "at the end")
                result["order_index"] = td.get("order_index", 0)
                found.append(result)
            else:
                not_found.append(f"{name} - {artist}" if artist else name)
        return {
            "tracks_to_add": found,
            "tracks_not_found": not_found,
            "total_found": len(found),
            "total_not_found": len(not_found),
        }

    def apply_changes(
        self, token_info: Dict[str, Any], playlist_id: str, track_suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Replace the playlist contents with the searched YouTube videos.

        Accepts either:
        - Pre-resolved tracks (from preview) that already have a 'uri' field → used directly.
        - Unresolved tracks with 'track_name'/'artist' → searched via YouTube Data API.
        """
        yt = self._client(token_info)
        found, not_found = [], []
        for td in track_suggestions:
            if not isinstance(td, dict):
                continue
            # Pre-resolved track from preview — reuse uri directly, no search needed
            if td.get("uri"):
                found.append(td)
                continue
            name = td.get("track_name", "").strip()
            artist = td.get("artist", "").strip()
            if not name:
                continue
            result = self.search_video(yt, name, artist)
            if result:
                result["position_instruction"] = td.get("position_instruction", "at the end")
                result["order_index"] = td.get("order_index", 0)
                found.append(result)
            else:
                not_found.append(f"{name} - {artist}" if artist else name)

        if not found:
            return {"success": False, "message": "No videos could be found on YouTube.", "not_found": not_found}

        try:
            # Clear ALL existing items (paginated — playlists can have > 50 items)
            page_token = None
            while True:
                kwargs: Dict[str, Any] = dict(part="id", playlistId=playlist_id, maxResults=50)
                if page_token:
                    kwargs["pageToken"] = page_token
                existing = yt.playlistItems().list(**kwargs).execute()
                for item in existing.get("items", []):
                    try:
                        yt.playlistItems().delete(id=item["id"]).execute()
                    except Exception as del_err:
                        print(f"WARNING: could not delete playlist item {item['id']}: {del_err}")
                page_token = existing.get("nextPageToken")
                if not page_token:
                    break

            # Add new videos
            for track in found:
                yt.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": track["uri"]},
                        }
                    },
                ).execute()

            # Invalidate the tracks cache for this playlist so next read is fresh
            self._tracks_cache_invalidate(playlist_id)

            return {
                "success": True,
                "added_count": len(found),
                "not_found_count": len(not_found),
                "added_tracks": found,
                "not_found_tracks": not_found,
            }
        except Exception as e:
            import traceback
            print(f"ERROR in YouTube apply_changes: {traceback.format_exc()}")
            return {"success": False, "message": str(e), "not_found": not_found}

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _creds_to_dict(creds: Credentials) -> Dict[str, Any]:
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "expires_at": time.time() + 3600,
            "scope": " ".join(_SCOPES),
            "source": "youtube",
        }

    def _client(self, token_info: Dict[str, Any]):
        creds = Credentials(
            token=token_info["access_token"],
            refresh_token=token_info.get("refresh_token"),
            token_uri=_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        return build("youtube", "v3", credentials=creds, cache_discovery=False)
