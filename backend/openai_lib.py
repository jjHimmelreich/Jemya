import re
import os
import json5 as json
from openai import OpenAI
import conf

os.environ['OPENAI_API_KEY'] = conf.OPENAI_API_KEY
model="gpt-4o"  # "gpt-4o" gpt-4o-mini

client = OpenAI()

def chat(messages):

    print ("Sending convo:" + json.dumps(messages))

    completion = client.chat.completions.create(
        model=model,
        messages=messages
    )

    message_content = completion.choices[0].message.content
    with open("completion.txt", "w") as f:
        f.write(message_content)

    print(message_content)
    return message_content


def generate_playlist(description):

    description = description + """Please analyze the conversation and extract last agreed tracks for Spotify playlist. 
    Please provide me with links to Spotify for the tracks if available. 
    Please format the response as json object so it can be easily parsed with Python.
    It should be objects list when the objects are in form of { "track_name": "", "artist": "", "duration": "", "spotify_link":"" }.
    """

    completion = client.chat.completions.create(
        model=model,
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

    empty_playlist = {"playlist": []}

    pattern = r"```(.*?)```"
    matches = re.findall(pattern, message_content, re.DOTALL)
    for match in matches:
        playlist = match
        playlist = playlist.replace('json', '')
    playlist_object = json.loads(playlist) if playlist else empty_playlist
    return playlist_object
