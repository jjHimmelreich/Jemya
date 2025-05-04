import json
import os
import datetime
DATA_DIR = "conversations"

def get_conversation(user_id, playlist_id=None):
    # Load existing conversation if it exists
    user_folder = os.path.join(DATA_DIR, user_id)
    os.makedirs(user_folder, exist_ok=True)
    convo_file = os.path.join(user_folder, "last_draft.json")

    if playlist_id:
        convo_file = os.path.join(user_folder, f"{playlist_id}.json")

    if os.path.exists(convo_file):
        with open(convo_file) as f:
            convo = json.load(f)
    else:

        format_ask = """General context of the conversation is going to be about music an generating playlists. 
        If the prompt will be about creating playlist or to providing list of tracks or something similar, please try to provide the tracks with links to Spotify. 
        The playlist or list of tracks, should be formatted as json object so i can easily parse it with Python. 
        The JSON should be objects list when the objects are in form of { "track_name": "", "artist": "", "duration": "" }."""

        convo = {
            # "user_id": user_id,
            # "conversation_id": datetime.datetime.utcnow().isoformat(),
            "messages": [
            {"role": "system", "content": "You are a helpful assistant.\n" + format_ask}
            ]
        }
    return convo

def update_sonversation(user_id, role='', content='', playlist_id=None):
    conversation = get_conversation(user_id, playlist_id=playlist_id)
    conversation["messages"].append({"role": role, "content": content})
    save_sonversation(user_id=user_id, conversation=conversation, playlist_id=playlist_id)
    return conversation

def save_sonversation(user_id, conversation, playlist_id=None):
    user_folder = os.path.join(DATA_DIR, user_id)
    os.makedirs(user_folder, exist_ok=True)
    convo_file = os.path.join(user_folder, "last_draft.json")
    
    if playlist_id:
        convo_file = os.path.join(user_folder, f"{playlist_id}.json")

    with open(convo_file, 'w') as f:
        json.dump(conversation, f, indent=2)
