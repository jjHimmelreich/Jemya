import re
import os
import json5 as json
import conf
from openai import OpenAI


os.environ['OPENAI_API_KEY'] = conf.OPENAI_API_KEY

DEBUG = False

client = OpenAI()


def chat_with_playlist(context):
    completion = client.chat.completions.create(
        model="gpt-4o",  # "gpt-4o" gpt-4o-mini
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": context
            }
        ]
    )

    message_content = completion.choices[0].message.content
    with open("completion.txt", "w") as f:
        f.write(message_content)

    print(message_content)
    return message_content


def generate_playlist(description):
    playlist = {"playlist": []}

    description = description + """Please analyze the conversation and extract last agreed tracks for Spotify playlist. Please provide me with links to Spotify for the tracks. 
    Please format the playlist as json object so i can easily parse it with Python.
    It should be objects list when the objects are in form of { "track_name": "", "artist": "", "duration": "" }.
    If you want to add comments, please add it as "comment" key in track object
    """

    completion = client.chat.completions.create(
        model="gpt-4o",  # "gpt-4o" gpt-4o-mini
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
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
