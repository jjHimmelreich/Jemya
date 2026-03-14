"""
Jemya FastAPI Backend
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
    """Start one persistent MCP server process for the lifetime of the app."""
    manager = MCPManager()
    try:
        await manager.connect()
        app.state.mcp_manager = manager
        logger.info("Persistent MCP server connected")
    except Exception as e:
        logger.error(f"Could not start persistent MCP server: {e}")
        app.state.mcp_manager = None

    yield  # ── app is running ──

    if app.state.mcp_manager:
        await manager.disconnect()
        logger.info("Persistent MCP server disconnected")


app = FastAPI(
    title="Jemya API",
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
    return {"status": "ok", "service": "jemya-api"}


# ── Serve compiled React frontend in production ───────────────────────────────
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Return index.html for all non-API routes (React SPA routing)."""
        return FileResponse(_DIST / "index.html")
