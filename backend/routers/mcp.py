"""
MCP router – cross-playlist operations via Model Context Protocol.
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException

from backend.models.schemas import MCPChatRequest
from backend.services.ai_service import get_ai_manager, get_mcp_manager

router = APIRouter(tags=["mcp"])


@router.post("/chat")
async def mcp_chat(body: MCPChatRequest) -> dict:
    """
    Send a user message that may trigger cross-playlist MCP tool calls.
    Returns the AI response, tool calls made, and tool results.
    """
    token_info = body.token_info
    if not token_info or "access_token" not in token_info:
        raise HTTPException(status_code=401, detail="Valid token_info required for MCP mode")

    access_token = token_info["access_token"]
    history = [m.model_dump(exclude_none=True) for m in body.conversation_history]

    try:
        async with get_mcp_manager(access_token) as mcp_manager:
            ai_manager = get_ai_manager(mcp_manager=mcp_manager)

            # Inject system message if missing
            if not any(m.get("role") == "system" for m in history):
                system_msg = ai_manager.generate_system_message(
                    has_spotify_connection=True, mcp_mode=True
                )
                history.insert(0, {"role": "system", "content": system_msg})

            result = await ai_manager.generate_with_mcp(
                user_message=body.user_message,
                conversation_history=history,
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
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
