"""Auth router – Spotify and YouTube OAuth flows."""
import logging
from fastapi import APIRouter, HTTPException

from backend.services.spotify_service import SpotifyService
from backend.services.youtube_service import YouTubeService
from backend.models.schemas import AuthCallbackRequest, RefreshTokenRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])
spotify = SpotifyService()
youtube = YouTubeService()


# ── Spotify ───────────────────────────────────────────────────────────────────

@router.get("/login-url")
def get_login_url() -> dict:
    """Return the Spotify OAuth authorization URL."""
    return {"auth_url": spotify.get_auth_url()}


@router.post("/callback")
def handle_callback(body: AuthCallbackRequest) -> dict:
    """Exchange auth code for access token."""
    try:
        token_info = spotify.get_token_from_code(body.code)
        return {"token_info": token_info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh")
def refresh_token(body: RefreshTokenRequest) -> dict:
    """Refresh an expired Spotify token."""
    refreshed = spotify.refresh_token_if_needed(body.token_info)
    if not refreshed:
        raise HTTPException(status_code=401, detail="Token refresh failed – please log in again.")
    return {"token_info": refreshed}


@router.post("/me")
def get_user_info(body: RefreshTokenRequest) -> dict:
    """Return the authenticated Spotify user's profile."""
    user = spotify.get_user_info(body.token_info)
    if not user:
        raise HTTPException(status_code=401, detail="Could not fetch user info.")
    return user


# ── YouTube ───────────────────────────────────────────────────────────────────

@router.get("/youtube/login-url")
def get_youtube_login_url() -> dict:
    """Return the Google OAuth authorization URL for YouTube access."""
    return {"auth_url": youtube.get_auth_url()}


@router.post("/youtube/callback")
def handle_youtube_callback(body: AuthCallbackRequest) -> dict:
    """Exchange Google auth code for YouTube access token."""
    try:
        token_info = youtube.get_token_from_code(body.code)
        return {"token_info": token_info}
    except Exception as e:
        logger.error("YouTube callback failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/youtube/refresh")
def refresh_youtube_token(body: RefreshTokenRequest) -> dict:
    """Refresh an expired YouTube token."""
    refreshed = youtube.refresh_token_if_needed(body.token_info)
    if not refreshed:
        raise HTTPException(status_code=401, detail="Token refresh failed – please log in again.")
    return {"token_info": refreshed}


@router.post("/youtube/me")
def get_youtube_user_info(body: RefreshTokenRequest) -> dict:
    """Return the authenticated YouTube user's channel info."""
    user = youtube.get_user_info(body.token_info)
    if not user:
        raise HTTPException(status_code=401, detail="Could not fetch YouTube user info.")
    return user
