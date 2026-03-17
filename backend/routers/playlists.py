"""
Playlists router – CRUD operations on Spotify and YouTube playlists.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from backend.services.spotify_service import SpotifyService
from backend.services.youtube_service import YouTubeService
from backend.models.schemas import (
    CreatePlaylistRequest,
    GetUserPlaylistsRequest,
    GetPlaylistTracksRequest,
    ApplyChangesRequest,
    PreviewChangesRequest,
)

router = APIRouter(tags=["playlists"])
spotify = SpotifyService()
youtube = YouTubeService()


# ── Spotify ───────────────────────────────────────────────────────────────────

@router.post("/")
def get_user_playlists(body: GetUserPlaylistsRequest) -> List[Dict[str, Any]]:
    """Return all playlists owned by the authenticated user."""
    playlists = spotify.get_user_playlists(body.token_info)
    # Normalize to a consistent shape
    return [
        {
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "description": p.get("description", ""),
            "public": p.get("public"),
            "images": p.get("images", []),
            "tracks_total": p.get("tracks", {}).get("total", 0) if p.get("tracks") else 0,
            "owner_id": p.get("owner", {}).get("id", ""),
            "owner_name": p.get("owner", {}).get("display_name") or p.get("owner", {}).get("id", "Unknown"),
        }
        for p in playlists
        if p
    ]


@router.post("/{playlist_id}/tracks")
def get_playlist_tracks(playlist_id: str, body: GetPlaylistTracksRequest) -> List[Dict[str, Any]]:
    """Return all tracks for the given playlist."""
    return spotify.get_playlist_tracks(body.token_info, playlist_id)


@router.post("/create")
def create_playlist(body: CreatePlaylistRequest) -> Dict[str, Any]:
    """Create a new playlist (Spotify or YouTube depending on token source)."""
    source = (body.token_info or {}).get("source", "spotify")
    if source == "youtube":
        success, message, playlist_id = youtube.create_playlist(
            body.token_info, body.name, body.description, body.public
        )
    else:
        success, message, playlist_id = spotify.create_playlist(
            body.token_info, body.name, body.description, body.public
        )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "playlist_id": playlist_id}


@router.post("/{playlist_id}/preview")
def preview_changes(playlist_id: str, body: PreviewChangesRequest) -> Dict[str, Any]:
    """Preview what tracks would be added/removed without modifying the playlist."""
    source = (body.token_info or {}).get("source", "spotify")
    if source == "youtube":
        return youtube.preview_changes(body.token_info, playlist_id, body.track_suggestions)
    return spotify.preview_changes(body.token_info, playlist_id, body.track_suggestions)


@router.post("/{playlist_id}/apply")
def apply_changes(playlist_id: str, body: ApplyChangesRequest) -> Dict[str, Any]:
    """Apply AI-suggested track changes to the playlist (Spotify or YouTube)."""
    source = (body.token_info or {}).get("source", "spotify")
    if source == "youtube":
        result = youtube.apply_changes(body.token_info, playlist_id, body.track_suggestions)
    else:
        result = spotify.apply_changes(body.token_info, playlist_id, body.track_suggestions)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Apply failed"))
    return result


# ── YouTube ───────────────────────────────────────────────────────────────────

@router.post("/youtube/")
def get_youtube_playlists(body: GetUserPlaylistsRequest) -> List[Dict[str, Any]]:
    """Return all YouTube playlists for the authenticated user."""
    return youtube.get_user_playlists(body.token_info)


@router.post("/youtube/{playlist_id}/tracks")
def get_youtube_playlist_tracks(playlist_id: str, body: GetPlaylistTracksRequest) -> List[Dict[str, Any]]:
    """Return all videos for the given YouTube playlist."""
    return youtube.get_playlist_tracks(body.token_info, playlist_id)


@router.post("/youtube/{playlist_id}/preview")
def preview_youtube_changes(playlist_id: str, body: PreviewChangesRequest) -> Dict[str, Any]:
    """Preview what YouTube videos would be added without modifying the playlist."""
    return youtube.preview_changes(body.token_info, playlist_id, body.track_suggestions)
