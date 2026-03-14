"""
AI / Chat router – non-MCP playlist enrichment via OpenAI.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.ai_service import get_ai_manager
from conversation_manager import ConversationManager

router = APIRouter(tags=["ai"])
conversation_manager = ConversationManager()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Send a user message for the current playlist conversation.
    Returns the AI response and any extracted track suggestions.
    """
    ai_manager = get_ai_manager()

    # Build conversation history list of dicts
    history = [m.model_dump(exclude_none=True) for m in body.conversation_history]

    # Load stored conversation if user_id + playlist_id provided
    if body.user_id and body.playlist_id:
        stored = conversation_manager.load_conversation(body.user_id, body.playlist_id)
        if stored and not history:
            history = stored.get("messages", [])

    # Ensure system message is present
    if not any(m.get("role") == "system" for m in history):
        system_msg = ai_manager.generate_system_message(
            has_spotify_connection=True, mcp_mode=False
        )
        history.insert(0, {"role": "system", "content": system_msg})

    # Add current playlist context if available
    if body.playlist_name and body.playlist_id:
        context = (
            f"The user is currently working on their Spotify playlist: "
            f"'{body.playlist_name}' (ID: {body.playlist_id}). "
            "Focus your suggestions on this playlist."
        )
        history.append({"role": "system", "content": context})

    history.append({"role": "user", "content": body.user_message})

    try:
        response = ai_manager.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=history,
        )
        assistant_content = response.choices[0].message.content

        # Persist conversation
        if body.user_id and body.playlist_id:
            history.append({"role": "assistant", "content": assistant_content})
            conversation_manager.save_conversation(
                body.user_id, body.playlist_id, history
            )

        # Extract track suggestions (lines that look like "Song - Artist")
        track_suggestions = [
            line.strip()
            for line in assistant_content.split("\n")
            if " - " in line or ("**" in line and "-" in line)
        ]

        return ChatResponse(
            response=assistant_content,
            track_suggestions=track_suggestions if track_suggestions else None,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-tracks")
async def extract_tracks(body: dict) -> dict:
    """
    Extract structured track list (name + artist JSON) from raw AI suggestion lines.
    """
    ai_manager = get_ai_manager()
    suggestions = body.get("track_suggestions", [])
    try:
        tracks = ai_manager.extract_tracks_from_ai_response(suggestions)
        return {"tracks": tracks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
