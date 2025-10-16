"""
Conversation Management Module
Handles saving/loading conversations and user sessions for the Jemya playlist generator.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional


class ConversationManager:
    """Manages user conversations and session state for playlist interactions."""
    
    def __init__(self, conversations_dir: str = "conversations"):
        self.conversations_dir = conversations_dir
        if not os.path.exists(conversations_dir):
            os.makedirs(conversations_dir)
    
    def get_conversation_file_path(self, user_id: str, playlist_id: str) -> str:
        """Generate file path for conversation storage"""
        return os.path.join(self.conversations_dir, f"{user_id}_{playlist_id}.json")
    
    def get_session_file_path(self, user_id: str) -> str:
        """Generate file path for session storage"""
        return os.path.join(self.conversations_dir, f"{user_id}_session.json")
    
    def save_user_session(self, user_id: str, current_playlist_id: Optional[str] = None, 
                         current_playlist_name: Optional[str] = None) -> None:
        """Save user's last session state"""
        try:
            file_path = self.get_session_file_path(user_id)
            session_data = {
                "user_id": user_id,
                "last_playlist_id": current_playlist_id,
                "last_playlist_name": current_playlist_name,
                "last_login_time": time.time()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            print(f"DEBUG: Saved session for user {user_id}, last playlist: {current_playlist_name}")
        except Exception as e:
            print(f"ERROR: Failed to save user session: {e}")
    
    def load_user_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load user's last session state"""
        try:
            file_path = self.get_session_file_path(user_id)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                print(f"DEBUG: Loaded session for user {user_id}, last playlist: {session_data.get('last_playlist_name')}")
                return session_data
        except Exception as e:
            print(f"ERROR: Failed to load user session: {e}")
        return None
    
    def save_conversation(self, user_id: str, playlist_id: str, messages: List[Dict[str, str]], 
                         playlist_snapshot: Optional[Dict[str, Any]] = None) -> None:
        """Save conversation to file with optional playlist snapshot"""
        try:
            file_path = self.get_conversation_file_path(user_id, playlist_id)
            
            # Try to load existing data to preserve playlist snapshot
            existing_snapshot = None
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        existing_snapshot = existing_data.get('playlist_snapshot')
                except Exception as e:
                    print(f"DEBUG: Could not load existing snapshot: {e}")
            
            conversation_data = {
                "user_id": user_id,
                "playlist_id": playlist_id,
                "messages": messages,
                "last_updated": time.time()
            }
            
            # Use provided snapshot, or preserve existing one
            if playlist_snapshot:
                conversation_data["playlist_snapshot"] = playlist_snapshot
                print(f"DEBUG: Saving with new playlist snapshot")
            elif existing_snapshot:
                conversation_data["playlist_snapshot"] = existing_snapshot
                print(f"DEBUG: Preserving existing playlist snapshot")
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            print(f"DEBUG: Saved conversation for user {user_id}, playlist {playlist_id}")
        except Exception as e:
            print(f"ERROR: Failed to save conversation: {e}")
    
    def load_conversation(self, user_id: str, playlist_id: str) -> List[Dict[str, str]]:
        """Load conversation from file"""
        try:
            file_path = self.get_conversation_file_path(user_id, playlist_id)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    conversation_data = json.load(f)
                print(f"DEBUG: Loaded conversation for user {user_id}, playlist {playlist_id} with {len(conversation_data.get('messages', []))} messages")
                return conversation_data.get('messages', [])
        except Exception as e:
            print(f"ERROR: Failed to load conversation: {e}")
        return []
    
    def has_conversation_changed(self, user_id: str, playlist_id: str, current_messages: List[Dict[str, str]]) -> bool:
        """Check if current conversation has changed from last saved version"""
        try:
            saved_messages = self.load_conversation(user_id, playlist_id)
            # Compare message count and content
            if len(saved_messages) != len(current_messages):
                return True
            
            # Compare each message
            for saved_msg, current_msg in zip(saved_messages, current_messages):
                if (saved_msg.get('role') != current_msg.get('role') or 
                    saved_msg.get('content') != current_msg.get('content')):
                    return True
            
            return False
        except Exception as e:
            print(f"DEBUG: Error checking conversation changes: {e}")
            return True  # If we can't compare, assume it changed to be safe
    
    def get_playlist_snapshot(self, playlist: Dict[str, Any], tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a snapshot of playlist for change detection"""
        return {
            "track_count": len(tracks),
            "track_ids": [track.get('id', '') for track in tracks if track.get('id')],
            "playlist_name": playlist.get('name', ''),
            "last_modified": playlist.get('snapshot_id', ''),  # Spotify's snapshot_id changes when playlist is modified
            "total_duration": sum(track.get('duration_ms', 0) for track in tracks)
        }
    
    def has_playlist_changed(self, user_id: str, playlist_id: str, current_playlist: Dict[str, Any], 
                           current_tracks: List[Dict[str, Any]]) -> bool:
        """Check if playlist content has changed since last save"""
        try:
            file_path = self.get_conversation_file_path(user_id, playlist_id)
            if not os.path.exists(file_path):
                return True  # No previous data, consider it changed
                
            with open(file_path, 'r', encoding='utf-8') as f:
                conversation_data = json.load(f)
                
            saved_snapshot = conversation_data.get('playlist_snapshot')
            if not saved_snapshot:
                return True  # No snapshot saved, consider it changed
                
            current_snapshot = self.get_playlist_snapshot(current_playlist, current_tracks)
            
            print(f"DEBUG: Comparing playlist snapshots for {playlist_id}:")
            print(f"DEBUG: Saved snapshot: {saved_snapshot}")
            print(f"DEBUG: Current snapshot: {current_snapshot}")
            
            # Compare key indicators of playlist changes
            track_count_changed = saved_snapshot.get('track_count') != current_snapshot.get('track_count')
            snapshot_id_changed = saved_snapshot.get('last_modified') != current_snapshot.get('last_modified')
            name_changed = saved_snapshot.get('playlist_name') != current_snapshot.get('playlist_name')
            duration_changed = saved_snapshot.get('total_duration') != current_snapshot.get('total_duration')
            
            changed = track_count_changed or snapshot_id_changed or name_changed or duration_changed
            
            if changed:
                print(f"DEBUG: Playlist {playlist_id} has changed:")
                print(f"  - Track count: {saved_snapshot.get('track_count')} -> {current_snapshot.get('track_count')} (changed: {track_count_changed})")
                print(f"  - Snapshot ID: {saved_snapshot.get('last_modified')} -> {current_snapshot.get('last_modified')} (changed: {snapshot_id_changed})")
                print(f"  - Name: {saved_snapshot.get('playlist_name')} -> {current_snapshot.get('playlist_name')} (changed: {name_changed})")
                print(f"  - Duration: {saved_snapshot.get('total_duration')} -> {current_snapshot.get('total_duration')} (changed: {duration_changed})")
            else:
                print(f"DEBUG: Playlist {playlist_id} unchanged since last load")
                
            return changed
            
        except Exception as e:
            print(f"ERROR: Failed to check playlist changes: {e}")
            return True  # If we can't compare, assume it changed
    
    def save_playlist_change_log(self, user_id: str, playlist_id: str, change_details: Dict[str, Any]) -> None:
        """Save a log of playlist changes for audit and rollback purposes"""
        try:
            log_file = os.path.join(self.conversations_dir, f"{user_id}_{playlist_id}_changes.json")
            
            # Load existing log or create new
            change_log = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        change_log = json.load(f)
                except Exception:
                    change_log = []
            
            # Add new change entry
            change_log.append({
                'timestamp': time.time(),
                'timestamp_readable': time.strftime('%Y-%m-%d %H:%M:%S'),
                'change_type': 'add_tracks',
                'details': change_details
            })
            
            # Keep only last 50 changes to prevent file from growing too large
            change_log = change_log[-50:]
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(change_log, f, ensure_ascii=False, indent=2)
            
            print(f"DEBUG: Saved playlist change log for {user_id}_{playlist_id}")
        except Exception as e:
            print(f"ERROR: Failed to save playlist change log: {e}")
    
    def get_recently_applied_tracks(self, user_id: str, playlist_id: str) -> set:
        """Get tracks that were recently applied to avoid re-application"""
        try:
            log_file = os.path.join(self.conversations_dir, f"{user_id}_{playlist_id}_changes.json")
            
            if not os.path.exists(log_file):
                return set()
            
            with open(log_file, 'r', encoding='utf-8') as f:
                change_log = json.load(f)
            
            # Get tracks applied in the last 10 minutes to prevent immediate re-application
            recent_cutoff = time.time() - 600  # 10 minutes
            recently_applied_uris = set()
            
            for entry in change_log:
                if entry.get('timestamp', 0) > recent_cutoff and entry.get('change_type') == 'add_tracks':
                    details = entry.get('details', {})
                    added_tracks = details.get('added_tracks', [])
                    for track in added_tracks:
                        if 'uri' in track:
                            recently_applied_uris.add(track['uri'])
            
            return recently_applied_uris
        except Exception as e:
            print(f"Error getting recently applied tracks: {e}")
            return set()
    
    def delete_conversation(self, user_id: str, playlist_id: str) -> bool:
        """Delete conversation file for a specific playlist"""
        try:
            file_path = self.get_conversation_file_path(user_id, playlist_id)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"DEBUG: Deleted conversation file for user {user_id}, playlist {playlist_id}")
                return True
            else:
                print(f"DEBUG: No conversation file found for user {user_id}, playlist {playlist_id}")
                return False
        except Exception as e:
            print(f"ERROR: Failed to delete conversation: {e}")
            return False