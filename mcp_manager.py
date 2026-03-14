"""
MCP Manager - Integration layer between Streamlit UI and Spotify MCP Server
Handles MCP client connection and converts tools for OpenAI function calling
"""
import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPManager:
    """Manager for MCP client connection and tool execution"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.session: Optional[ClientSession] = None
        self.client_context = None
        self.tools_cache: Optional[List[Dict]] = None
        self._server_params = StdioServerParameters(
            command="python3.11",
            args=["spotify_mcp_server.py"],
            env=None
        )
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    async def connect(self):
        """Connect to the MCP server"""
        if self.session:
            return
        
        try:
            logger.info("Connecting to Spotify MCP server...")
            # Use stdio_client as async context manager
            self.client_context = stdio_client(self._server_params)
            streams = await self.client_context.__aenter__()
            read_stream, write_stream = streams
            self.session = ClientSession(read_stream, write_stream)
            await self.session.__aenter__()
            
            # Initialize the MCP session
            await self.session.initialize()
            
            logger.info("Connected to MCP server successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
                if self.client_context:
                    await self.client_context.__aexit__(None, None, None)
                self.session = None
                self.client_context = None
                logger.info("Disconnected from MCP server")
            except Exception as e:
                logger.error(f"Error disconnecting from MCP server: {e}")
    
    async def get_tools_for_openai(self) -> List[Dict]:
        """Convert MCP tools to OpenAI function calling format"""
        if self.tools_cache:
            return self.tools_cache
        
        if not self.session:
            await self.connect()
        
        try:
            # Get tools from MCP server
            tools_response = await self.session.list_tools()
            
            # Convert to OpenAI format
            openai_tools = []
            for tool in tools_response.tools:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                openai_tools.append(openai_tool)
            
            self.tools_cache = openai_tools
            logger.info(f"Loaded {len(openai_tools)} MCP tools for OpenAI")
            return openai_tools
            
        except Exception as e:
            logger.error(f"Failed to get MCP tools: {e}")
            raise
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any],
                           access_token: Optional[str] = None) -> Any:
        """Execute a single MCP tool"""
        if not self.session:
            await self.connect()
        
        try:
            # Prefer explicitly passed token (for per-request isolation on shared instance)
            token = access_token or self.access_token
            if token and "access_token" not in arguments:
                arguments["access_token"] = token
            
            logger.info(f"Executing tool: {tool_name}")
            result = await self.session.call_tool(tool_name, arguments)
            
            # Parse the result (MCP returns TextContent)
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    return json.loads(content.text)
            
            return {"error": "No content returned from tool"}
            
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}")
            # Mark session as dead so next call triggers a reconnect
            self.session = None
            self.client_context = None
            return {"error": str(e)}
    
    async def execute_tool_calls(self, tool_calls: List,
                                  access_token: Optional[str] = None) -> List[Dict]:
        """Execute multiple OpenAI function calls via MCP"""
        results = []
        
        for call in tool_calls:
            try:
                arguments = json.loads(call.function.arguments)
                result = await self.execute_tool(call.function.name, arguments,
                                                 access_token=access_token)
                
                # Summarize result to reduce context size
                summarized_result = self.summarize_tool_result(call.function.name, result)
                
                results.append({
                    "tool_call_id": call.id,
                    "role": "tool",
                    "name": call.function.name,
                    "content": json.dumps(summarized_result)
                })
            except Exception as e:
                logger.error(f"Failed to execute tool call {call.function.name}: {e}")
                results.append({
                    "tool_call_id": call.id,
                    "role": "tool",
                    "name": call.function.name,
                    "content": json.dumps({"error": str(e)})
                })
        
        return results
    
    @staticmethod
    def is_write_operation(tool_name: str) -> bool:
        """Check if a tool is a write operation that needs confirmation"""
        write_ops = {'create_playlist', 'add_tracks', 'remove_tracks', 'replace_playlist'}
        return tool_name in write_ops
    
    @staticmethod
    def extract_write_operations(tool_calls: List) -> List[Dict[str, Any]]:
        """Extract write operations from tool calls for preview
        
        Args:
            tool_calls: List of OpenAI tool calls
            
        Returns:
            List of write operations with their details
        """
        writes = []
        for call in tool_calls:
            if MCPManager.is_write_operation(call.function.name):
                try:
                    arguments = json.loads(call.function.arguments)
                    writes.append({
                        "tool_call_id": call.id,
                        "operation": call.function.name,
                        "arguments": arguments,
                        "raw_call": call
                    })
                except Exception as e:
                    logger.error(f"Failed to parse write operation {call.function.name}: {e}")
        return writes
    
    @staticmethod
    def summarize_tool_result(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize tool results to reduce context size
        
        Args:
            tool_name: Name of the tool that was called
            result: Raw result from tool execution
            
        Returns:
            Summarized result with only essential information
        """
        if tool_name == "list_playlists" and "playlists" in result:
            # Data is already pre-summarized by the MCP server; pass through as-is
            return result
        
        elif tool_name == "read_playlist" and "tracks" in result:
            # For playlist tracks, keep essential fields but can be verbose
            tracks = result["tracks"]
            summarized_tracks = []
            for t in tracks:
                summarized_tracks.append({
                    "name": t.get("track_name") or t.get("name"),
                    "artist": t.get("artist"),
                    "uri": t.get("uri")
                })
            return {
                "playlist_id": result.get("playlist_id"),
                "name": result.get("name"),
                "track_count": result.get("track_count"),
                "tracks": summarized_tracks
            }
        
        # For other tools, return as-is
        return result
    
    def update_access_token(self, access_token: str):
        """Update the Spotify access token"""
        self.access_token = access_token


# Synchronous wrapper functions for Streamlit
class MCPManagerSync:
    """Synchronous wrapper for MCPManager to use in Streamlit"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self._manager: Optional[MCPManager] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop for async operations"""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def _run_async(self, coro):
        """Run async function synchronously"""
        loop = self._get_or_create_loop()
        return loop.run_until_complete(coro)
    
    def connect(self):
        """Connect to MCP server (sync)"""
        if not self._manager:
            self._manager = MCPManager(self.access_token)
        self._run_async(self._manager.connect())
    
    def disconnect(self):
        """Disconnect from MCP server (sync)"""
        if self._manager:
            self._run_async(self._manager.disconnect())
    
    def get_tools_for_openai(self) -> List[Dict]:
        """Get OpenAI-formatted tools (sync)"""
        if not self._manager:
            self.connect()
        return self._run_async(self._manager.get_tools_for_openai())
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute tool (sync)"""
        if not self._manager:
            self.connect()
        return self._run_async(self._manager.execute_tool(tool_name, arguments))
    
    def execute_tool_calls(self, tool_calls: List) -> List[Dict]:
        """Execute multiple tool calls (sync)"""
        if not self._manager:
            self.connect()
        return self._run_async(self._manager.execute_tool_calls(tool_calls))
    
    def update_access_token(self, access_token: str):
        """Update access token (sync)"""
        self.access_token = access_token
        if self._manager:
            self._manager.update_access_token(access_token)
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
