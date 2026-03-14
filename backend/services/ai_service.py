"""
AI Service for FastAPI backend.
Wraps ai_manager.py – no Streamlit dependencies.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ai_manager import AIManager
from mcp_manager import MCPManager

_ai_instance = AIManager()


def get_ai_manager(mcp_manager=None) -> AIManager:
    if mcp_manager is not None:
        return AIManager(mcp_manager=mcp_manager)
    return _ai_instance


def get_mcp_manager(access_token: str) -> MCPManager:
    return MCPManager(access_token=access_token)
