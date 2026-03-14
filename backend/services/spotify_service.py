"""
Spotify Service
All methods accept token_info as an explicit parameter.
"""
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import configuration_manager as conf


class SpotifyService:
    """Stateless Spotify API service – all state is passed in, nothing stored internally."""

    def __init__(self):
        self.client_id = conf.SPOTIFY_CLIENT_ID
        self.client_secret = conf.SPOTIFY_CLIENT_SECRET
        self.redirect_uri = conf.SPOTIFY_REDIRECT_URI
        self.scope = (
            "user-read-playback-state user-library-read "
            "playlist-read-private playlist-read-collaborative "
            "playlist-modify-public playlist-modify-private "
            "user-modify-playback-state"
        )
        self.cache_path = ".spotify_token_cache"

    # ── Auth ──────────────────────────────────────────────────────────────────

    def get_spotify_oauth(self) -> SpotifyOAuth:
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=self.cache_path,
        )

    def get_auth_url(self) -> str:
        return self.get_spotify_oauth().get_authorize_url()

    def get_token_from_code(self, code: str) -> Dict[str, Any]:
        return self.get_spotify_oauth().get_access_token(code, as_dict=True)

    def refresh_token_if_needed(self, token_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a (possibly refreshed) token_info dict. No side effects."""
        if not token_info or not isinstance(token_info, dict):
            return None
        if "expires_at" not in token_info:
            return token_info

        if time.time() > token_info["expires_at"] - 30:
            try:
                sp_oauth = self.get_spotify_oauth()
                return sp_oauth.refresh_access_token(token_info["refresh_token"])
            except Exception as e:
                print(f"ERROR: Token refresh failed: {e}")
                return None

        return token_info

    def _client(self, token_info: Dict[str, Any]) -> spotipy.Spotify:
        """Return an authenticated Spotipy client for the given token."""
        token_info = self.refresh_token_if_needed(token_info) or token_info
        return spotipy.Spotify(auth=token_info["access_token"])

    # ── User ─────────────────────────────────────────────────────────────────

    def get_user_info(self, token_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            return self._client(token_info).current_user()
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None

    # ── Playlists ─────────────────────────────────────────────────────────────

    def get_user_playlists(self, token_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            sp = self._client(token_info)
            return self._fetch_all_playlists(sp)
        except Exception as e:
            print(f"Error in get_user_playlists: {e}")
            return []

    @staticmethod
    def _fetch_all_playlists(sp: spotipy.Spotify) -> List[Dict[str, Any]]:
        playlists, offset, limit = [], 0, 50
        while True:
            response = sp.current_user_playlists(offset=offset, limit=limit)
            if not response or "items" not in response:
                break
            playlists.extend(response["items"])
            if len(response["items"]) < limit:
                break
            offset += limit
        return playlists

    def get_playlist_tracks(self, token_info: Dict[str, Any], playlist_id: str) -> List[Dict[str, Any]]:
        try:
            sp = self._client(token_info)
            tracks, offset, limit = [], 0, 100
            while True:
                response = sp.playlist_tracks(playlist_id, offset=offset, limit=limit)
                if not response or "items" not in response:
                    break
                for item in response["items"]:
                    if item and item.get("track"):
                        t = item["track"]
                        if t and t.get("name"):
                            tracks.append({
                                "id": t.get("id", ""),
                                "name": t.get("name", "Unknown"),
                                "artists": ", ".join(a.get("name", "") for a in t.get("artists", [])),
                                "album": t.get("album", {}).get("name", "Unknown"),
                                "duration_ms": t.get("duration_ms", 0),
                                "popularity": t.get("popularity", 0),
                                "explicit": t.get("explicit", False),
                                "spotify_url": t.get("external_urls", {}).get("spotify", ""),
                                "uri": t.get("uri", ""),
                            })
                if len(response["items"]) < limit:
                    break
                offset += limit
            return tracks
        except Exception as e:
            print(f"Error in get_playlist_tracks: {e}")
            return []

    def create_playlist(
        self, token_info: Dict[str, Any], name: str, description: str = "", public: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        try:
            sp = self._client(token_info)
            user_id = sp.current_user()["id"]
            playlist = sp.user_playlist_create(user=user_id, name=name, public=public, description=description)
            return True, f"Playlist '{name}' created successfully!", playlist["id"]
        except Exception as e:
            return False, f"Failed to create playlist: {e}", None

    # ── Track Search ──────────────────────────────────────────────────────────

    def search_track_with_flexible_matching(
        self, sp: spotipy.Spotify, track_name: str, artist_name: str
    ) -> Optional[Dict[str, Any]]:
        """Try multiple search strategies and return the first match."""
        strategies = [
            f'track:"{track_name}" artist:"{artist_name}"',
            f"track:{track_name} artist:{artist_name}",
            f'"{track_name}" "{artist_name}"',
            f"{track_name} {artist_name}",
            track_name,
        ]
        for query in strategies:
            try:
                results = sp.search(q=query, type="track", limit=5)
                items = results.get("tracks", {}).get("items", [])
                if items:
                    return items[0]
            except Exception:
                continue
        return None

    def search_and_validate_tracks(
        self, token_info: Dict[str, Any], tracks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        sp = self._client(token_info)
        results, not_found = [], []
        for td in tracks:
            if not isinstance(td, dict):
                continue
            name = td.get("track_name", "").strip()
            artist = td.get("artist", "").strip()
            if not name or not artist:
                continue
            found = self.search_track_with_flexible_matching(sp, name, artist)
            if found:
                results.append({
                    "uri": found["uri"],
                    "found_name": found["name"],
                    "found_artist": ", ".join(a["name"] for a in found["artists"]),
                    "found_album": found["album"]["name"],
                    "duration_ms": found["duration_ms"],
                    "spotify_url": found["external_urls"]["spotify"],
                    "position_instruction": td.get("position_instruction", "at the end"),
                    "order_index": td.get("order_index", 0),
                })
            else:
                not_found.append(f"{name} - {artist}")
        return results, not_found

    # ── Playlist Modification ─────────────────────────────────────────────────

    def preview_changes(
        self, token_info: Dict[str, Any], playlist_id: str, track_suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Return a preview of what would change without modifying Spotify."""
        found, not_found = self.search_and_validate_tracks(token_info, track_suggestions)
        return {
            "tracks_to_add": found,
            "tracks_not_found": not_found,
            "total_found": len(found),
            "total_not_found": len(not_found),
        }

    def apply_changes(
        self, token_info: Dict[str, Any], playlist_id: str, track_suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply track suggestions to the playlist (full replace strategy)."""
        sp = self._client(token_info)
        user_id = sp.current_user()["id"]

        found, not_found = self.search_and_validate_tracks(token_info, track_suggestions)
        if not found:
            return {"success": False, "message": "No tracks could be found on Spotify.", "not_found": not_found}

        uris = [t["uri"] for t in found]

        try:
            # Replace all tracks
            sp.user_playlist_replace_tracks(user_id, playlist_id, uris[:100])
            for i in range(100, len(uris), 100):
                sp.user_playlist_add_tracks(user_id, playlist_id, uris[i:i + 100])

            return {
                "success": True,
                "added_count": len(found),
                "not_found_count": len(not_found),
                "added_tracks": found,
                "not_found_tracks": not_found,
            }
        except Exception as e:
            return {"success": False, "message": str(e), "not_found": not_found}
