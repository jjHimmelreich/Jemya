"""
Auth router – Spotify OAuth flow.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from backend.services.spotify_service import SpotifyService
from backend.models.schemas import AuthCallbackRequest, RefreshTokenRequest, TokenInfo

router = APIRouter(tags=["auth"])
spotify = SpotifyService()


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
