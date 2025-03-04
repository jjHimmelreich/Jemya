from flask import Flask, request, redirect, session, url_for, render_template, jsonify
import spotify_api  # Import your Spotify module
import openai_api  # Import your OpenAI module
import random
import string
import os
import json
import datetime
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management
# Directory to store conversation JSON files
CONVERSATIONS_DIR = 'conversations'
if not os.path.exists(CONVERSATIONS_DIR):
    os.makedirs(CONVERSATIONS_DIR)


@app.route('/', methods=['GET', 'POST'])
def index():
    playlist_name = None
    tracks = None
    playlist_url = None
    playlist_description = None
    if request.method == 'POST' and 'playlist_url' in request.form:
        playlist_url = request.form['playlist_url']
        session['playlist_url'] = playlist_url
        # Call the actual process_playlist function from spotify_api
        playlist_name, tracks = spotify_api.process_playlist(playlist_url)
    elif 'playlist_url' in session:
        playlist_url = session['playlist_url']
        playlist_name, tracks = spotify_api.process_playlist(playlist_url)
    if 'playlist_description' in session:
        playlist_description = session['playlist_description']
    return render_template('index.html', playlist_name=playlist_name, tracks=tracks, playlist_url=playlist_url, playlist_description=playlist_description, session=session)


@app.route('/login')
def login():
    sp_oauth = spotify_api.get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
def callback():
    sp_oauth = spotify_api.get_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    # Fetch Spotify account information
    user_info = spotify_api.get_user_info(token_info)
    session['user_name'] = user_info['display_name']
    session['user_id'] = user_info['id']
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/playlists', methods=['GET'])
def get_playlists():
    token_info = session.get('token_info')
    if not token_info:
        return jsonify(playlists=[])
    playlists = spotify_api.get_user_playlists(token_info)
    return jsonify(playlists=playlists)


@app.route('/playlist_tracks/<playlist_id>', methods=['GET'])
def get_playlist_tracks(playlist_id):
    token_info = session.get('token_info')
    if not token_info:
        return jsonify(tracks=[], total_tracks=0, total_duration="0:00")
    tracks, total_tracks, total_duration = spotify_api.get_playlist_tracks(
        playlist_id, token_info)
    return jsonify(tracks=tracks, total_tracks=total_tracks, total_duration=total_duration)


@app.route('/conversations', methods=['GET'])
def get_conversations():
    conversations = []
    for filename in os.listdir(CONVERSATIONS_DIR):
        if filename.endswith('.json'):
            conversations.append(filename[:-5])  # Remove .json extension
    return jsonify(conversations=conversations)


@app.route('/conversation/<name>', methods=['GET'])
def get_conversation(name):
    filepath = os.path.join(CONVERSATIONS_DIR, f"{name}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            conversation = json.load(file)
        return jsonify(conversation=conversation)
    else:
        return jsonify(conversation=[])


@app.route('/send_message', methods=['POST'])
def send_message():
    prompt = request.form['prompt']
    conversation_name = request.form.get('conversation_name')
    playlist_context = request.form.get('playlist_context', '')
    if not conversation_name:
        # Generate a new conversation name if none is provided
        conversation_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filepath = os.path.join(CONVERSATIONS_DIR, f"{conversation_name}.json")
    # Load existing conversation or create a new one
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            conversation = json.load(file)
    else:
        # Create a new conversation if none exists
        conversation = []
    # Add the playlist content as a system message if it's not already present
    if not any(message['role'] == 'system' for message in conversation):
        system_message = {"role": "system", "content": playlist_context}
        conversation.insert(0, system_message)
    # Append the new user message to the conversation
    conversation.append({"role": "user", "content": prompt})
    # Add the conversation history to the context
    context = ""
    for message in conversation:
        context += f"\n{message['role'].capitalize()}: {message['content']}"
    # Call the OpenAI API to get the response
    response, proposal = openai_api.chat_with_playlist(context)
    # Append the new bot response to the conversation
    conversation.append({"role": "bot", "content": response})
    # Save the updated conversation
    with open(filepath, 'w') as file:
        json.dump(conversation, file)
    return jsonify(response=response, conversation_name=conversation_name, proposal=proposal)


@app.route('/apply_proposal', methods=['POST'])
def apply_proposal():
    proposal = request.form['proposal']
    conversation_name = request.form.get('conversation_name')
    token_info = session.get('token_info')
    # Fetch the current state of the playlist
    tracks, total_tracks, total_duration = spotify_api.get_playlist_tracks(
        conversation_name, token_info)
    # Call the OpenAI API to generate the playlist based on the proposal
    generated_playlist = openai_api.generate_playlist(proposal)
    # Create a playlist on Spotify with the generated tracks
    playlist_url = spotify_api.create_playlist(
        conversation_name, generated_playlist, token_info)
    return jsonify(success=True, playlist_url=playlist_url, tracks=tracks, total_tracks=total_tracks, total_duration=total_duration)


@app.route('/load_conversation', methods=['GET'])
def load_conversation():
    conversation_name = request.args.get('conversation_name')
    filepath = os.path.join(CONVERSATIONS_DIR, f"{conversation_name}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            conversation = json.load(file)
        return jsonify(conversation=conversation)
    else:
        return jsonify(conversation=[])


if __name__ == '__main__':
    app.run(debug=True, port=5555, host='0.0.0.0')
