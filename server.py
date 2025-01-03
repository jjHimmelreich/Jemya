from flask import Flask, request, redirect, session, url_for, render_template, jsonify, make_response, send_from_directory
import spotify_api  # Import your Spotify module
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/', methods=['GET', 'POST'])
def index():
    playlist_name = None
    tracks = None
    playlist_url = None
    if request.method == 'POST':
        playlist_url = request.form['playlist_url']
        session['playlist_url'] = playlist_url
        # Call the actual process_playlist function from spotify_api
        playlist_name, tracks = spotify_api.process_playlist(playlist_url)
    elif 'playlist_url' in session:
        playlist_url = session['playlist_url']
        playlist_name, tracks = spotify_api.process_playlist(playlist_url)
    return render_template('index.html', playlist_name=playlist_name, tracks=tracks, playlist_url=playlist_url)

@app.route('/login')
def login():
    # sp_oauth = spotify_api.get_spotify_oauth()
    # auth_url = sp_oauth.get_authorize_url()
    # return redirect(auth_url)
    sp_oauth = spotify_api.get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    response = make_response(redirect(auth_url))
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    return response

@app.route('/callback')
def callback():
    sp_oauth = spotify_api.get_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('index'))

@app.route('/play', methods=['POST'])
def play():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect(url_for('login'))
    track_id = request.json['track_id']
    spotify_api.play_track(track_id, token_info)
    return jsonify(success=True)

@app.route('/pause', methods=['POST'])
def pause():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect(url_for('login'))
    track_id = request.json['track_id']
    spotify_api.pause_track(track_id, token_info)
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True, port=5555)