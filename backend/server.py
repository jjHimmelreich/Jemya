import utils
import conversation_manager
import openai_lib
import spotify_lib
from flask import Flask, request, jsonify, session, redirect
from flask_cors import CORS
import datetime

import json
import os

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devsecret")
CORS(app, supports_credentials=True, origins="http://localhost:3000")

DATA_DIR = "conversations"
os.makedirs(DATA_DIR, exist_ok=True)

# @app.route('/favicon.ico')
# def favicon():
#     return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/login")
def login():
    # sp_oauth = spotify_lib.get_spotify_oauth()
    # auth_url = sp_oauth.get_authorize_url()
    # return jsonify({"auth_url": auth_url})
    sp_oauth = spotify_lib.get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/logout', methods=["POST"])
def logout():
    session.clear()
    return redirect("http://localhost:3000")  # Frontend home
    # return redirect(url_for('index'))


@app.route("/callback")
def callback():
    sp_oauth = spotify_lib.get_spotify_oauth()
    session.clear()
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info

    user_info = spotify_lib.get_user_info(token_info)
    user_id = spotify_lib.get_user_id(token_info)
    user_name = spotify_lib.get_user_name(token_info)

    print("user_info="+json.dumps(user_info))

    session['user_name'] = user_name
    session['user_id'] = user_id

    return redirect("http://localhost:3000")  # Frontend home
    # return redirect(url_for('index'))


@app.route("/me")
def me():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    return jsonify({
        "user_id": session['user_id'],
        "user_name": session.get('user_name', "Unknown")
    })


@app.route("/chat", methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    prompt = request.json.get("prompt")
    user_id = session['user_id']

    # Load existing conversation if it exists
    convo = conversation_manager.get_conversation(user_id)

    # Add user's prompt to the conversation
    convo = conversation_manager.add_to_conversation(
        user_id=user_id, role="user", content=prompt)

    # Send full conversation to OpenAI
    gpt_text = openai_lib.chat(convo["messages"])

    # Add gpt reply to the conversation
    convo = conversation_manager.add_to_conversation(
        user_id=user_id, role="assistant", content=gpt_text)

    return jsonify({
        "result": gpt_text
    })

@app.route("/playlists", methods=['GET'])
def get_playlists():
    if 'user_id' not in session or 'token_info' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    token_info = session['token_info']    

    playlists = spotify_lib.get_user_playlists(token_info=token_info)

    return jsonify({"playlists": playlists})


@app.route("/playlist", methods=['PUT'])
def create_playlist():
    if 'user_id' not in session or 'token_info' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    token_info = session['token_info']    
    playlist_name = request.json.get("name")

    playlist_url, playlist_id = spotify_lib.create_playlist(token_info=token_info, 
                                                            playlist_name=playlist_name)

    return jsonify({
        "playlist_url": playlist_url,
        "playlist_id": playlist_id
    })

@app.route("/playlist", methods=['POST'])
def confirm_playlist():
    if 'user_id' not in session or 'token_info' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    token_info = session['token_info']

    # Step 1: Load previous draft
    convo = conversation_manager.get_conversation(user_id=user_id)

    gpt_text = convo["messages"][-1]["content"]

    # Step 2: Create playlist on Spotify

    playlist_name = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    parsed_json, text_before, text_after = utils.extract_playlist(gpt_text)
    playlist_url, playlist_id, tracks = spotify_lib.generate_playlist(token_info=token_info,
                                                                      playlist_name=playlist_name,
                                                                      tracks_list=parsed_json)
    # Step 3: All manual gpt resp with external call data:
    convo = conversation_manager.add_to_conversation(user_id=user_id,
                                                     role='assistant',
                                                     extra_kv={
                                                         "type": "function",
                                                         "function": {
                                                             "name": "spotify_lib.generate_playlist",
                                                             "arguments": json.dumps({"playlist_name": {playlist_name}, "tracks_list": parsed_json})
                                                         }
                                                     },
                                                     content=None)

    # Step 4: Update and save full conversation
    convo = conversation_manager.add_to_conversation(user_id=user_id,
                                                     role='tool',
                                                     extra_kv={
                                                         "tool_call_id": "spotify_lib.generate_playlist"},
                                                     content=json.dumps({"playlist_url": playlist_url, "playlisy_id": playlist_id, "tracks": json.dumps(tracks)})
                                                    )

    # conversation_manager.save_sonversation(user_id=user_id,
    #                                        conversation = convo,
    #                                        playlist_id=playlist_id)

    return jsonify({
        "playlist_url": playlist_url,
        "tracks": tracks
    })


if __name__ == "__main__":
    app.run(debug=True, port=5555, host='0.0.0.0', use_reloader=False)
