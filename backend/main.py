"""
Jemya FastAPI Backend
Run with: uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import auth, playlists, ai, mcp

app = FastAPI(
    title="Jemya API",
    description="AI Playlist Generator – FastAPI backend",
    version="2.0.0",
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
