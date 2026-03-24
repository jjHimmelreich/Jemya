#!/usr/bin/env python3.11
"""
YouTube MCP Server
Exposes YouTube playlist operations as Model Context Protocol (MCP) tools.
Uses YouTube Data API v3 via google-api-python-client.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import configuration_manager as conf
from backend.services.youtube_service import YouTubeService

_yt_service = YouTubeService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_YT_TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeMCPServer:
    """MCP Server wrapper for YouTube playlist operations."""

    def __init__(self):
        self.server = Server("youtube-mcp-server")
        self._setup_tools()

    def _get_youtube_client(self, access_token: str):
        """Build an authenticated YouTube API client from a bearer access_token."""
        creds = Credentials(
            token=access_token,
            token_uri=_YT_TOKEN_URI,
            client_id=conf.YOUTUBE_CLIENT_ID,
            client_secret=conf.YOUTUBE_CLIENT_SECRET,
        )
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def _fetch_all_playlist_items(self, yt, playlist_id: str) -> List[Dict]:
        """Fetch every item from a playlist (handles pagination)."""
        items = []
        page_token = None
        while True:
            kwargs = dict(part="snippet,contentDetails", playlistId=playlist_id, maxResults=50)
            if page_token:
                kwargs["pageToken"] = page_token
            resp = yt.playlistItems().list(**kwargs).execute()
            items.extend(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items

    def _setup_tools(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="get_current_user",
                    description=(
                        "Get the current authenticated user's YouTube channel info (channel ID and title). "
                        "Call this first when you need to identify 'my playlists'."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"}
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="list_playlists",
                    description=(
                        "List all YouTube playlists owned by the authenticated user. "
                        "Returns playlist IDs, titles, and video counts."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"}
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="read_playlist",
                    description=(
                        "Get all videos from a specific YouTube playlist. "
                        "IMPORTANT: You must provide an exact YouTube playlist ID (like 'PLxxxxxxxx'), NOT a name. "
                        "Use list_playlists() first to find the playlist ID."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {
                                "type": "string",
                                "description": "Exact YouTube playlist ID. Get this from list_playlists() first.",
                            },
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"},
                        },
                        "required": ["playlist_id"],
                    },
                ),
                Tool(
                    name="search_tracks",
                    description=(
                        "Search for music videos on YouTube by name and artist. "
                        "Returns video_ids to use with add_tracks. "
                        "Note: search is quota-limited — keep queries targeted."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (song name, artist, or combination)",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Maximum number of results (default: 10, max: 25)",
                            },
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"},
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="create_playlist",
                    description="Create a new YouTube playlist.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the new playlist"},
                            "description": {
                                "type": "string",
                                "description": "Description of the playlist",
                            },
                            "public": {
                                "type": "boolean",
                                "description": "Whether the playlist is public (default: false)",
                            },
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"},
                        },
                        "required": ["name"],
                    },
                ),
                Tool(
                    name="add_tracks",
                    description=(
                        "Add videos to a YouTube playlist by their video IDs. "
                        "Use video_ids obtained from search_tracks. Skips duplicates automatically."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {"type": "string", "description": "The YouTube playlist ID"},
                            "video_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of YouTube video IDs to add (e.g. ['dQw4w9WgXcQ'])",
                            },
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"},
                        },
                        "required": ["playlist_id", "video_ids"],
                    },
                ),
                Tool(
                    name="remove_tracks",
                    description="Remove videos from a YouTube playlist by their video IDs.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {"type": "string", "description": "The YouTube playlist ID"},
                            "video_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of YouTube video IDs to remove",
                            },
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"},
                        },
                        "required": ["playlist_id", "video_ids"],
                    },
                ),
                Tool(
                    name="replace_playlist",
                    description="Replace all videos in a YouTube playlist with a new set of videos.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "playlist_id": {"type": "string", "description": "The YouTube playlist ID"},
                            "video_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of YouTube video IDs for the new playlist content",
                            },
                            "access_token": {"type": "string", "description": "YouTube OAuth access token"},
                        },
                        "required": ["playlist_id", "video_ids"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                logger.info(f"Executing tool: {name}")
                dispatch = {
                    "get_current_user": self._get_current_user,
                    "list_playlists": self._list_playlists,
                    "read_playlist": self._read_playlist,
                    "search_tracks": self._search_tracks,
                    "create_playlist": self._create_playlist,
                    "add_tracks": self._add_tracks,
                    "remove_tracks": self._remove_tracks,
                    "replace_playlist": self._replace_playlist,
                }
                if name not in dispatch:
                    raise ValueError(f"Unknown tool: {name}")
                result = await dispatch[name](arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # ── Tool implementations ──────────────────────────────────────────────────

    async def _get_current_user(self, args: Dict[str, Any]) -> Dict[str, Any]:
        yt = self._get_youtube_client(args["access_token"])
        resp = yt.channels().list(part="snippet", mine=True, maxResults=1).execute()
        items = resp.get("items", [])
        if not items:
            return {"error": "No YouTube channel found for this account"}
        channel = items[0]
        return {
            "channel_id": channel["id"],
            "title": channel["snippet"]["title"],
            "description": channel["snippet"].get("description", ""),
        }

    async def _list_playlists(self, args: Dict[str, Any]) -> Dict[str, Any]:
        yt = self._get_youtube_client(args["access_token"])
        playlists = []
        page_token = None
        while True:
            kwargs = dict(part="snippet,contentDetails,status", mine=True, maxResults=50)
            if page_token:
                kwargs["pageToken"] = page_token
            resp = yt.playlists().list(**kwargs).execute()
            for p in resp.get("items", []):
                playlists.append({
                    "id": p["id"],
                    "name": p["snippet"]["title"],
                    "description": p["snippet"].get("description", ""),
                    "track_count": p["contentDetails"]["itemCount"],
                    "privacy": p.get("status", {}).get("privacyStatus", "unknown"),
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return {"count": len(playlists), "playlists": playlists}

    async def _read_playlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = args["playlist_id"]
        access_token = args["access_token"]
        # Build a minimal token_info so YouTubeService can build a client
        token_info = {"access_token": access_token, "source": "youtube"}
        try:
            # Use YouTubeService which goes through the tracks cache
            raw_tracks = _yt_service.get_playlist_tracks(token_info, playlist_id)
            tracks = [
                {
                    "position": idx + 1,
                    "track_name": t.get("name", "Unknown"),
                    "video_id": t.get("uri", ""),
                    "channel_title": t.get("artists", ""),
                }
                for idx, t in enumerate(raw_tracks)
            ]

            # Get playlist name — use cached playlists list first to avoid a free API call
            pl_name = playlist_id
            cached_playlists = _yt_service._playlists_cache_get(
                _yt_service._playlists_cache_key(token_info)
            )
            if cached_playlists:
                match = next((p for p in cached_playlists if p["id"] == playlist_id), None)
                if match:
                    pl_name = match["name"]
            if pl_name == playlist_id:
                # Fall back to API if not in cache
                yt = self._get_youtube_client(access_token)
                pl_resp = yt.playlists().list(part="snippet", id=playlist_id).execute()
                pl_items = pl_resp.get("items", [])
                if pl_items:
                    pl_name = pl_items[0]["snippet"]["title"]

            return {
                "playlist_id": playlist_id,
                "name": pl_name,
                "track_count": len(tracks),
                "tracks": tracks,
            }
        except Exception as e:
            return {"error": "read_failed", "playlist_id": playlist_id, "message": str(e)}

    async def _search_tracks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args["query"]
        limit = min(int(args.get("limit", 10)), 25)
        access_token = args["access_token"]
        token_info = {"access_token": access_token, "source": "youtube"}
        yt = self._get_youtube_client(access_token)

        # Split combined queries (e.g. "Song A, Song B") into individual searches
        # so each result can be cached independently, then return up to `limit` results.
        sub_queries = [q.strip() for q in query.replace(";", ",").split(",") if q.strip()] or [query]
        tracks = []
        for sq in sub_queries[:limit]:
            # Derive track_name / artist from the sub-query for cache key consistency
            parts = sq.split(" by ", 1) if " by " in sq else sq.split(" - ", 1)
            track_name = parts[0].strip()
            artist_name = parts[1].strip() if len(parts) > 1 else ""
            result = _yt_service.search_video(yt, track_name, artist_name)
            if result:
                tracks.append({
                    "track_name": result["found_name"],
                    "channel_title": result["found_artist"],
                    "video_id": result["uri"],
                    "url": result["spotify_url"],
                })
            if len(tracks) >= limit:
                break

        return {"query": query, "results": tracks, "count": len(tracks)}

    async def _create_playlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        yt = self._get_youtube_client(args["access_token"])
        privacy = "public" if args.get("public", False) else "private"
        body = {
            "snippet": {
                "title": args["name"],
                "description": args.get("description", ""),
            },
            "status": {"privacyStatus": privacy},
        }
        resp = yt.playlists().insert(part="snippet,status", body=body).execute()
        return {
            "success": True,
            "playlist_id": resp["id"],
            "name": resp["snippet"]["title"],
            "url": f"https://www.youtube.com/playlist?list={resp['id']}",
        }

    async def _add_tracks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = args["playlist_id"]
        video_ids = args["video_ids"]
        yt = self._get_youtube_client(args["access_token"])

        # Deduplicate: skip videos already in the playlist
        existing = {
            item["snippet"]["resourceId"]["videoId"]
            for item in self._fetch_all_playlist_items(yt, playlist_id)
            if item.get("snippet", {}).get("resourceId", {}).get("kind") == "youtube#video"
        }

        added, skipped = 0, 0
        for vid in video_ids:
            if vid in existing:
                skipped += 1
                continue
            yt.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": vid},
                    }
                },
            ).execute()
            added += 1

        return {
            "success": True,
            "playlist_id": playlist_id,
            "added_count": added,
            "skipped_duplicates": skipped,
        }

    async def _remove_tracks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = args["playlist_id"]
        video_ids = set(args["video_ids"])
        yt = self._get_youtube_client(args["access_token"])

        # Map videoId → playlistItemId for targeted deletion
        items = self._fetch_all_playlist_items(yt, playlist_id)
        to_delete = [
            item["id"]
            for item in items
            if item.get("snippet", {}).get("resourceId", {}).get("videoId") in video_ids
        ]

        for item_id in to_delete:
            yt.playlistItems().delete(id=item_id).execute()

        return {
            "success": True,
            "playlist_id": playlist_id,
            "removed_count": len(to_delete),
        }

    async def _replace_playlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = args["playlist_id"]
        video_ids = args["video_ids"]
        yt = self._get_youtube_client(args["access_token"])

        # Delete all current items
        current_items = self._fetch_all_playlist_items(yt, playlist_id)
        for item in current_items:
            yt.playlistItems().delete(id=item["id"]).execute()

        # Insert new items
        for vid in video_ids:
            yt.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": vid},
                    }
                },
            ).execute()

        return {
            "success": True,
            "playlist_id": playlist_id,
            "removed_count": len(current_items),
            "added_count": len(video_ids),
        }

    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            logger.info("YouTube MCP Server started")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    server = YouTubeMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
