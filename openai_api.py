from openai import OpenAI
import conf
import json5 as json
import os
import re

os.environ['OPENAI_API_KEY'] = conf.OPENAI_API_KEY

DEBUG = False

client = OpenAI()

def chat_with_playlist(context):
    if DEBUG:
        message_content = conf.DEMO_PLAYLIST
        proposal = "This is a demo proposal."
    else:
        completion = client.chat.completions.create(
            model="gpt-4o", #"gpt-4o" gpt-4o-mini
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": context
                }
            ]
        )
        message_content = completion.choices[0].message.content
        proposal = extract_proposal(message_content)
        with open("completion.txt", "w") as f:
            f.write(message_content)
    print(message_content)
    return message_content, proposal

def extract_proposal(message_content):
    # Extract the proposal from the message content
    # This is a placeholder implementation. You may need to adjust it based on the actual response format.
    proposal = re.search(r"Proposal:(.*)", message_content, re.DOTALL)
    if proposal:
        return proposal.group(1).strip()
    return None

def generate_playlist(description):
    
    if DEBUG:
        message_content = conf.DEMO_PLAYLIST
    else:
        playlist = {"playlist": []}

        description = description + """Please provide me with links to spotify for every track. 
        Please format the playlist as json object so i can easily parse it with python.
        It should be objects list when the objects are in form of { "track_name": "", "artist": "", "duration": "" }.
        If you want to add comments, please add it as "comment" key in track object
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o", #"gpt-4o" gpt-4o-mini
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    # "content": """Please build playlist of music like la mer by Laura fygi. 
                    # The playlist should be around 2hours and 30 minutes
                    # Please make it suitable for contact improvisation jam
                    # It should be two BPM spikes of one track only with immediate drop after. First spike should be around 30 minutes from the beginning of the playlist and second one at around 1.5 hour.
                    # For BPM spikes, you can use absolutely different music like trance, drums, rock-n-roll, swing, twist...
                    # Ideally, please provide me with links to spotify for every track.
                    # Please format the playlist as json object so i can easily parse it with python."""
                    "content": description
                }
            ]
        )

        message_content = completion.choices[0].message.content
        with open("completion.txt", "w") as f:
            f.write(message_content)

    print(message_content)

    pattern = r"```(.*?)```"
    matches = re.findall(pattern, message_content, re.DOTALL)

    for match in matches:
      playlist = match
      playlist = playlist.replace('json', '')

    playlist_object = json.loads(playlist)
    return playlist_object