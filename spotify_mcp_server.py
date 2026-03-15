#!/usr/bin/env python3.11
"""
Spotify MCP Server
Exposes Spotify operations as Model Context Protocol (MCP) tools
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import MemoryCacheHandler
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import configuration_manager as conf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpotifyMCPServer:
    """MCP Server wrapper for Spotify operations"""
    
    def __init__(self):
        self.server = Server("spotify-mcp-server")
        self.sp: Optional[spotipy.Spotify] = None
        self._setup_tools()
    
    def _get_spotify_client(self, access_token: Optional[str] = None) -> spotipy.Spotify:
        """Get authenticated Spotify client"""
        if access_token:
            return spotipy.Spotify(auth=access_token)
        
        # Fallback to OAuth flow (access_token is always provided in production)
        auth_manager = SpotifyOAuth(
            client_id=conf.SPOTIFY_CLIENT_ID,
            client_secret=conf.SPOTIFY_CLIENT_SECRET,
            redirect_uri=conf.SPOTIFY_REDIRECT_URI,
            scope="user-read-playback-state user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-modify-playback-state",
            cache_handler=MemoryCacheHandler(),
        )
        return spotipy.Spotify(auth_manager=auth_manager)
    
    def _setup_tools(self):
        """Register all MCP tools"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available Spotify MCP tools"""
            return [
                Tool(
                    name="read_playlist",
                    description="Get all tracks from a specific Spotify playlist. IMPORTANT: You must provide an exact Spotify playlist ID (like '37i9dQZF1DXcBWIGoYBM5M'), NOT a name or pattern. Use list_playlists() first to find the playlist ID.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {
                                "type": "string",
                                "description": "Exact Spotify playlist ID (NOT a name, pattern, or wildcard). Get this ID from list_playlists() first."
                            },
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            }
                        },
                        "required": ["playlist_id"]
                    }
                ),
                Tool(
                    name="get_current_user",
                    description="Get the current authenticated Spotify user's profile, including their user ID and display name. Call this first when you need to filter playlists by owner or identify 'my playlists'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "access_token": {
                                "type": "string",
                                "description": "Spotify access token"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="list_playlists",
                    description="List playlists for the authenticated user with automatic paging. Returns ALL playlists by default. Use owner_id to filter server-side to only playlists created by a specific user (get the ID from get_current_user first).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            },
                            "owner_id": {
                                "type": "string",
                                "description": "If provided, return only playlists where owner_id matches this value. Use get_current_user() to get the current user's ID when filtering for 'my playlists'."
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="search_tracks",
                    description="Search for tracks on Spotify by name and artist",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (track name, artist, or combination)"
                            },
                            "limit": {
                                "type": "number",
                                "description": "Maximum number of results (default: 10)"
                            },
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="create_playlist",
                    description="Create a new Spotify playlist",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the new playlist"
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of the playlist"
                            },
                            "public": {
                                "type": "boolean",
                                "description": "Whether the playlist is public (default: false)"
                            },
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="add_tracks",
                    description="Add tracks to a Spotify playlist",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {
                                "type": "string",
                                "description": "The Spotify playlist ID"
                            },
                            "track_uris": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of Spotify track URIs to add"
                            },
                            "position": {
                                "type": "number",
                                "description": "Position to insert tracks (default: end of playlist)"
                            },
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            }
                        },
                        "required": ["playlist_id", "track_uris"]
                    }
                ),
                Tool(
                    name="remove_tracks",
                    description="Remove tracks from a Spotify playlist",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {
                                "type": "string",
                                "description": "The Spotify playlist ID"
                            },
                            "track_uris": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of Spotify track URIs to remove"
                            },
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            }
                        },
                        "required": ["playlist_id", "track_uris"]
                    }
                ),
                Tool(
                    name="replace_playlist",
                    description="Replace all tracks in a playlist with new ones",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {
                                "type": "string",
                                "description": "The Spotify playlist ID"
                            },
                            "track_uris": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of Spotify track URIs for the new playlist content"
                            },
                            "access_token": {
                                "type": "string",
                                "description": "Optional Spotify access token for authentication"
                            }
                        },
                        "required": ["playlist_id", "track_uris"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a tool call"""
            try:
                logger.info(f"Executing tool: {name} with arguments: {arguments}")
                
                if name == "get_current_user":
                    result = await self._get_current_user(arguments)
                elif name == "read_playlist":
                    result = await self._read_playlist(arguments)
                elif name == "list_playlists":
                    result = await self._list_playlists(arguments)
                elif name == "search_tracks":
                    result = await self._search_tracks(arguments)
                elif name == "create_playlist":
                    result = await self._create_playlist(arguments)
                elif name == "add_tracks":
                    result = await self._add_tracks(arguments)
                elif name == "remove_tracks":
                    result = await self._remove_tracks(arguments)
                elif name == "replace_playlist":
                    result = await self._replace_playlist(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)})
                )]
    
    async def _read_playlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read all tracks from a playlist"""
        playlist_id = args["playlist_id"]
        access_token = args.get("access_token")
        
        sp = self._get_spotify_client(access_token)
        
        try:
            tracks = []
            offset = 0
            limit = 100
            
            while True:
                results = sp.playlist_tracks(
                    playlist_id,
                    offset=offset,
                    limit=limit,
                    fields='items(track(id,name,artists(name),uri,duration_ms)),next,total'
                )
                
                if not results or 'items' not in results:
                    break
                
                for idx, item in enumerate(results['items']):
                    if item and 'track' in item and item['track']:
                        track = item['track']
                        tracks.append({
                            'position': offset + idx + 1,
                            'track_name': track['name'],
                            'artist': ', '.join([artist['name'] for artist in track.get('artists', [])]),
                            'uri': track['uri'],
                            'duration_ms': track.get('duration_ms', 0)
                        })
            
                if not results.get('next'):
                    break
                
                offset += limit
            
            # Get playlist info
            playlist_info = sp.playlist(playlist_id, fields='name,owner.display_name,tracks.total')
            
            return {
                'playlist_id': playlist_id,
                'name': playlist_info['name'],
                'owner': playlist_info['owner']['display_name'],
                'track_count': len(tracks),
                'tracks': tracks
            }
            
        except Exception as e:
            # Handle 404 (deleted/inaccessible playlists) and other errors gracefully
            error_message = str(e)
            if '404' in error_message or 'not found' in error_message.lower():
                return {
                    'error': 'playlist_not_found',
                    'playlist_id': playlist_id,
                    'message': f'Playlist {playlist_id} not found or inaccessible. It may have been deleted or you may not have permission to access it.'
                }
            else:
                return {
                    'error': 'read_failed',
                    'playlist_id': playlist_id,
                    'message': f'Failed to read playlist: {error_message}'
                }
    
    async def _get_current_user(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current authenticated user's profile"""
        access_token = args.get("access_token")
        sp = self._get_spotify_client(access_token)
        me = sp.current_user()
        return {
            "user_id": me.get("id"),
            "display_name": me.get("display_name") or me.get("id"),
            "email": me.get("email"),
        }

    async def _list_playlists(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List user's playlists with full pagination and optional owner filtering"""
        access_token = args.get("access_token")
        owner_id_filter = args.get("owner_id")  # Server-side filter
        
        sp = self._get_spotify_client(access_token)
        
        # Fetch all playlists with pagination
        raw = []
        offset = 0
        page_limit = 50
        while True:
            response = sp.current_user_playlists(offset=offset, limit=page_limit)
            if not response or 'items' not in response:
                break
            # Spotify can return null items for inaccessible playlists — skip them
            raw.extend([p for p in response['items'] if p is not None])
            if len(response['items']) < page_limit:
                break
            offset += page_limit
        
        # Return only the fields the AI needs — keeps the stdio payload small
        playlists = []
        for p in raw:
            owner = p.get("owner") or {}
            playlists.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "track_count": (p.get("tracks") or {}).get("total", 0),
                "owner_id": owner.get("id"),
                "owner_name": owner.get("display_name") or owner.get("id"),
                "public": p.get("public"),
                "collaborative": p.get("collaborative"),
            })
        
        # Apply server-side owner filter if requested
        if owner_id_filter:
            playlists = [p for p in playlists if p["owner_id"] == owner_id_filter]
        
        return {
            'count': len(playlists),
            'total_before_filter': len(raw) if owner_id_filter else len(playlists),
            'playlists': playlists
        }
    
    async def _search_tracks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for tracks"""
        query = args["query"]
        limit = args.get("limit", 10)
        access_token = args.get("access_token")
        
        sp = self._get_spotify_client(access_token)
        
        results = sp.search(q=query, type='track', limit=limit)
        
        tracks = []
        for track in results['tracks']['items']:
            tracks.append({
                'track_name': track['name'],
                'artist': ', '.join([artist['name'] for artist in track['artists']]),
                'uri': track['uri'],
                'album': track['album']['name'],
                'duration_ms': track['duration_ms']
            })
        
        return {
            'query': query,
            'count': len(tracks),
            'tracks': tracks
        }
    
    async def _create_playlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new playlist"""
        name = args["name"]
        description = args.get("description", "")
        public = args.get("public", False)
        access_token = args.get("access_token")
        
        sp = self._get_spotify_client(access_token)
        
        user_id = sp.current_user()['id']
        playlist = sp.user_playlist_create(
            user=user_id,
            name=name,
            public=public,
            description=description
        )
        
        return {
            'success': True,
            'playlist_id': playlist['id'],
            'name': playlist['name'],
            'url': playlist['external_urls']['spotify']
        }
    
    async def _add_tracks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add tracks to playlist, skipping any URIs already present (idempotent)."""
        playlist_id = args["playlist_id"]
        track_uris = args["track_uris"]
        position = args.get("position")
        access_token = args.get("access_token")

        sp = self._get_spotify_client(access_token)

        # Fetch current track URIs to avoid adding duplicates
        existing_uris: set = set()
        results = sp.playlist_items(playlist_id, fields='items(track(uri)),next', limit=100)
        while results:
            for item in (results.get('items') or []):
                track = (item or {}).get('track')
                if track and track.get('uri'):
                    existing_uris.add(track['uri'])
            results = sp.next(results) if results.get('next') else None

        new_uris = [u for u in track_uris if u not in existing_uris]
        skipped_count = len(track_uris) - len(new_uris)

        # Add in batches of 100
        added_count = 0
        for i in range(0, len(new_uris), 100):
            batch = new_uris[i:i+100]
            sp.playlist_add_items(playlist_id, batch, position=position)
            added_count += len(batch)

        return {
            'success': True,
            'playlist_id': playlist_id,
            'added_count': added_count,
            'skipped_duplicates': skipped_count,
        }
    
    async def _remove_tracks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Remove tracks from playlist"""
        playlist_id = args["playlist_id"]
        track_uris = args["track_uris"]
        access_token = args.get("access_token")
        
        sp = self._get_spotify_client(access_token)
        
        user_id = sp.current_user()['id']
        
        # Remove in batches of 100
        removed_count = 0
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            sp.user_playlist_remove_all_occurrences_of_tracks(user_id, playlist_id, batch)
            removed_count += len(batch)
        
        return {
            'success': True,
            'playlist_id': playlist_id,
            'removed_count': removed_count
        }
    
    async def _replace_playlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Replace all tracks in playlist"""
        playlist_id = args["playlist_id"]
        track_uris = args["track_uris"]
        access_token = args.get("access_token")
        
        sp = self._get_spotify_client(access_token)
        
        # First, get current tracks to count them
        current_tracks = []
        offset = 0
        while True:
            results = sp.playlist_tracks(playlist_id, offset=offset, limit=100, fields='items(track(uri)),next')
            if not results or 'items' not in results:
                break
            for item in results['items']:
                if item and 'track' in item and item['track']:
                    current_tracks.append(item['track']['uri'])
            if not results.get('next'):
                break
            offset += 100
        
        # Remove all current tracks
        user_id = sp.current_user()['id']
        if current_tracks:
            for i in range(0, len(current_tracks), 100):
                batch = current_tracks[i:i+100]
                sp.user_playlist_remove_all_occurrences_of_tracks(user_id, playlist_id, batch)
        
        # Add new tracks
        if track_uris:
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]
                sp.playlist_add_items(playlist_id, batch)
        
        return {
            'success': True,
            'playlist_id': playlist_id,
            'removed_count': len(current_tracks),
            'added_count': len(track_uris)
        }
    
    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Spotify MCP Server started")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    server = SpotifyMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
