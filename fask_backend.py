# flask_backend.py
from flask import Flask, request, jsonify, session, redirect, send_from_directory
from flask_cors import CORS
import os, json, datetime
from spotify_lib import get_auth_url, exchange_code, get_user_id, generate_playlist
from openai import ChatCompletion

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devsecret")
CORS(app, supports_credentials=True)

DATA_DIR = "conversations"
os.makedirs(DATA_DIR, exist_ok=True)

# @app.route('/favicon.ico')
# def favicon():
#     return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/login")
def login():
    auth_url = get_auth_url()
    return jsonify({"auth_url": auth_url})

@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = exchange_code(code)
    user_id = get_user_id(token_info)

    session['user_id'] = user_id
    session['token_info'] = token_info
    return redirect("http://127.0.0.1:5173")  # Frontend home

@app.route("/me")
def me():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"user_id": session['user_id']})

@app.route("/generate-playlist", methods=['POST'])
def generate():
    if 'user_id' not in session or 'token_info' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    token_info = session['token_info']
    prompt = request.json.get("prompt")

    # Step 1: Get GPT response
    chat_prompt = f"Generate a mood/genre/activity summary and playlist idea from: {prompt}"
    gpt_response = ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": chat_prompt}]
    )
    gpt_text = gpt_response.choices[0].message.content

    # Step 2: Use your Spotify lib to create playlist and return info
    playlist_url, tracks = generate_playlist(token_info, gpt_text)

    # Step 3: Save conversation
    convo = {
        "user_id": user_id,
        "conversation_id": datetime.datetime.utcnow().isoformat(),
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "gpt", "content": gpt_text},
            {
                "role": "spotify",
                "playlist_url": playlist_url,
                "tracks": tracks
            }
        ]
    }
    user_folder = os.path.join(DATA_DIR, user_id)
    os.makedirs(user_folder, exist_ok=True)
    filename = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S") + ".json"
    with open(os.path.join(user_folder, filename), 'w') as f:
        json.dump(convo, f, indent=2)

    return jsonify({
        "gpt_reply": gpt_text,
        "playlist_url": playlist_url,
        "tracks": tracks
    })

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')