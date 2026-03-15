"""
MCP router – cross-playlist operations via Model Context Protocol.
"""
import logging
import time
import traceback
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

from backend.models.schemas import MCPChatRequest
from backend.services.ai_service import get_ai_manager
from conversation_manager import ConversationManager

router = APIRouter(tags=["mcp"])
_conversation_manager = ConversationManager()


@router.post("/chat")
async def mcp_chat(body: MCPChatRequest, request: Request) -> dict:
    """
    Send a user message that may trigger cross-playlist MCP tool calls.
    Returns the AI response, tool calls made, and tool results.
    """
    token_info = body.token_info
    if not token_info or "access_token" not in token_info:
        raise HTTPException(status_code=401, detail="Valid token_info required for MCP mode")

    # Raise 401 if the token is already expired so the frontend refreshes it.
    # We must NOT refresh here — a backend-side refresh discards the new
    # token_info (including the rotated refresh_token) and the frontend would
    # later fail to refresh with the stale token it still holds.
    expires_at = token_info.get("expires_at")
    if expires_at and time.time() > float(expires_at):
        raise HTTPException(status_code=401, detail="Spotify token expired – please refresh")

    access_token = token_info["access_token"]

    history = [m.model_dump(exclude_none=True) for m in body.conversation_history]

    # Use the persistent MCP manager from app state (started once at startup)
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    # mcp_manager may be None if the MCP server failed to start (e.g. missing
    # config).  In that case we fall back to plain OpenAI without tool calls so
    # the user still gets AI assistance, just without live Spotify tool access.

    try:
        ai_manager = get_ai_manager(mcp_manager=mcp_manager)

        # Inject system message if missing
        if not any(m.get("role") == "system" for m in history):
            system_msg = ai_manager.generate_system_message(
                has_spotify_connection=True, mcp_mode=mcp_manager is not None
            )
            history.insert(0, {"role": "system", "content": system_msg})

        # Inject active playlist context so AI knows which playlist to target
        if body.playlist_id:
            active_ctx = (
                f"\n\nACTIVE PLAYLIST:\n"
                f"• Name: {body.playlist_name}\n"
                f"• Spotify ID: `{body.playlist_id}`\n"
                f"When the user asks to enrich or modify this playlist, read it with read_playlist(`{body.playlist_id}`), "
                f"analyze the tracks, search for additions with search_tracks(), then output the COMPLETE final "
                f"tracklist as 'Track Name - Artist' lines (every track in order). "
                f"Do NOT call add_tracks, remove_tracks, or replace_playlist — those tools are not available. "
                f"The user will review your proposed tracklist and apply it with the Preview & Save button."
            )
            for msg in history:
                if msg.get("role") == "system":
                    msg["content"] += active_ctx
                    break

        if mcp_manager is not None:
            result = await ai_manager.generate_with_mcp(
                user_message=body.user_message,
                conversation_history=history,
                access_token=access_token,
            )
        else:
            # MCP server unavailable — plain OpenAI call (no Spotify tools)
            logger.warning("MCP server unavailable, falling back to plain OpenAI")
            messages = history + [{"role": "user", "content": body.user_message}]
            response = ai_manager.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=8192,
            )
            assistant_content = response.choices[0].message.content
            result = {"response": assistant_content, "tool_calls": [], "tool_results": []}

        # Persist the conversation after every successful response
        if body.user_id and body.playlist_id:
            save_messages = history + [
                {"role": "user", "content": body.user_message},
                {"role": "assistant", "content": result.get("response", "")},
            ]
            _conversation_manager.save_conversation(
                body.user_id, body.playlist_id, save_messages
            )

        return {
            "response": result.get("response", ""),
            "tool_calls": [
                {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in result.get("tool_calls", [])
            ],
            "tool_results": result.get("tool_results", []),
            "max_iterations_reached": result.get("max_iterations_reached", False),
            # Extract track suggestions so the frontend Preview→Apply flow works.
            # Lines of the form "Track Name - Artist" are treated as proposals.
            "track_suggestions": [
                line.strip()
                for line in result.get("response", "").split("\n")
                if " - " in line or ("**" in line and "-" in line)
            ] or None,
        }

    except Exception as e:
        logger.error("mcp_chat exception: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
