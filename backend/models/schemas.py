"""
Pydantic models for request/response schemas.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenInfo(BaseModel):
    access_token: str
    token_type: str
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    scope: Optional[str] = None


class AuthCallbackRequest(BaseModel):
    code: str


class RefreshTokenRequest(BaseModel):
    token_info: Dict[str, Any]


# ── User ──────────────────────────────────────────────────────────────────────

class UserInfo(BaseModel):
    id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    images: Optional[List[Dict[str, Any]]] = None


# ── Playlists ─────────────────────────────────────────────────────────────────

class PlaylistItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    public: Optional[bool] = None
    images: Optional[List[Dict[str, Any]]] = None
    tracks_total: Optional[int] = None
    owner_id: Optional[str] = None


class TrackItem(BaseModel):
    id: Optional[str] = None
    name: str
    artists: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    popularity: Optional[int] = None
    explicit: Optional[bool] = None
    spotify_url: Optional[str] = None
    uri: Optional[str] = None


class CreatePlaylistRequest(BaseModel):
    token_info: Dict[str, Any]
    name: str
    description: Optional[str] = ""
    public: Optional[bool] = False


class GetPlaylistTracksRequest(BaseModel):
    token_info: Dict[str, Any]


class GetUserPlaylistsRequest(BaseModel):
    token_info: Dict[str, Any]


class ApplyChangesRequest(BaseModel):
    token_info: Dict[str, Any]
    playlist_id: str
    track_suggestions: List[Dict[str, Any]]


class PreviewChangesRequest(BaseModel):
    token_info: Dict[str, Any]
    playlist_id: str
    track_suggestions: List[Dict[str, Any]]


# ── AI / Chat ─────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str  # "user" | "assistant" | "system" | "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    token_info: Dict[str, Any]
    user_message: str
    conversation_history: List[Message] = []
    playlist_id: Optional[str] = None
    playlist_name: Optional[str] = None
    user_id: Optional[str] = None
    mcp_mode: bool = False


class ChatResponse(BaseModel):
    response: str
    track_suggestions: Optional[List[str]] = None  # raw AI lines that contain tracks


# ── MCP ───────────────────────────────────────────────────────────────────────

class MCPChatRequest(BaseModel):
    token_info: Dict[str, Any]
    user_message: str
    conversation_history: List[Message] = []
    user_id: Optional[str] = None
    playlist_id: Optional[str] = None
    playlist_name: Optional[str] = None


class MCPWriteOperation(BaseModel):
    operation: str
    playlist_id: Optional[str] = None
    playlist_name: Optional[str] = None
    track_uris: Optional[List[str]] = None
    description: Optional[str] = None


class MCPConfirmRequest(BaseModel):
    token_info: Dict[str, Any]
    operations: List[MCPWriteOperation]


# ── Conversations ─────────────────────────────────────────────────────────────

class SaveConversationRequest(BaseModel):
    user_id: str
    playlist_id: str
    messages: List[Message]
    playlist_snapshot: Optional[Dict[str, Any]] = None


class LoadConversationRequest(BaseModel):
    user_id: str
    playlist_id: str
