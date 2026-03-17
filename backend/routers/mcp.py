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
    expires_at = token_info.get("expires_at")
    if expires_at and time.time() > float(expires_at):
        source_label = token_info.get("source", "Spotify")
        raise HTTPException(status_code=401, detail=f"{source_label} token expired – please refresh")

    access_token = token_info["access_token"]
    source = token_info.get("source", "spotify")  # 'spotify' or 'youtube'

    history = [m.model_dump(exclude_none=True) for m in body.conversation_history]

    # Select the persistent MCP manager for the correct source
    if source == "youtube":
        mcp_manager = getattr(request.app.state, "yt_mcp_manager", None)
    else:
        mcp_manager = getattr(request.app.state, "mcp_manager", None)
    # mcp_manager may be None if the MCP server failed to start (e.g. missing
    # config).  In that case we fall back to plain OpenAI without tool calls so
    # the user still gets AI assistance, just without live Spotify tool access.

    try:
        ai_manager = get_ai_manager(mcp_manager=mcp_manager)

        # Inject system message if missing
        if not any(m.get("role") == "system" for m in history):
            system_msg = ai_manager.generate_system_message(
                has_spotify_connection=True, mcp_mode=mcp_manager is not None, source=source
            )
            history.insert(0, {"role": "system", "content": system_msg})

        # Inject active playlist context so AI knows which playlist to target
        if body.playlist_id:
            id_label = "YouTube playlist ID" if source == "youtube" else "Spotify ID"
            active_ctx = (
                f"\n\nACTIVE PLAYLIST:\n"
                f"• Name: {body.playlist_name}\n"
                f"• {id_label}: `{body.playlist_id}`\n"
                f"For any modification request on this playlist you MUST:\n"
                f"  1. Call read_playlist(`{body.playlist_id}`) to get the current full tracklist.\n"
                f"  2. Compute the desired final state (add, remove, reorder — whatever was asked).\n"
                f"  3. Output EVERY track in the final playlist as plain 'Track Name - Artist' lines "
                f"(one per line, in order). Include ALL existing tracks that should remain PLUS all new ones.\n"
                f"  Example: user asks to add 1 track to a 10-track playlist → your output has 11 lines.\n"
                f"  Example: user asks to remove 1 track from a 10-track playlist → your output has 9 lines.\n"
                f"The Preview & Save Changes button sends your ENTIRE output to replace the playlist. "
                f"Any track you omit will be permanently deleted."
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
