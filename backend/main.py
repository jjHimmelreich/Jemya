"""
Jam-ya FastAPI Backend
Run with: uvicorn backend.main:app --reload --port 8000
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.routers import auth, playlists, ai, mcp
from mcp_manager import MCPManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start persistent MCP server processes for Spotify and YouTube."""
    import configuration_manager as conf

    spotify_manager = MCPManager(source="spotify")
    try:
        await spotify_manager.connect()
        app.state.mcp_manager = spotify_manager
        logger.info("Spotify MCP server connected")
    except Exception as e:
        logger.error("Could not start Spotify MCP server: %s", e)
        app.state.mcp_manager = None

    # Only start YouTube MCP if credentials are configured
    app.state.yt_mcp_manager = None
    if conf.YOUTUBE_CLIENT_ID:
        yt_manager = MCPManager(source="youtube")
        try:
            await yt_manager.connect()
            app.state.yt_mcp_manager = yt_manager
            logger.info("YouTube MCP server connected")
        except Exception as e:
            logger.error("Could not start YouTube MCP server: %s", e)
    else:
        logger.info("YouTube credentials not configured — skipping YouTube MCP server")

    yield  # ── app is running ──

    if app.state.mcp_manager:
        await spotify_manager.disconnect()
        logger.info("Spotify MCP server disconnected")
    if app.state.yt_mcp_manager:
        await app.state.yt_mcp_manager.disconnect()
        logger.info("YouTube MCP server disconnected")


app = FastAPI(
    title="Jam-ya API",
    description="AI Playlist Generator – FastAPI backend",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow the React dev server (port 5173 for Vite) and production origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5555",
        "http://127.0.0.1:5555",
        "http://localhost:5173",  # Vite default fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(playlists.router, prefix="/playlists")
app.include_router(ai.router, prefix="/ai")
app.include_router(mcp.router, prefix="/mcp")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "jam-ya-api"}


# ── Serve compiled React frontend in production ───────────────────────────────
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve static files from dist, falling back to index.html for SPA routes."""
        requested = _DIST / full_path
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(_DIST / "index.html")
