from flask import Flask, request, render_template, jsonify
import spotify_api  # Import your Spotify module

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    playlist_name = None
    tracks = None
    playlist_url = None
    if request.method == 'POST':
        playlist_url = request.form['playlist_url']
        # Call the actual process_playlist function from spotify_api
        playlist_name, tracks = spotify_api.process_playlist(playlist_url)
    return render_template('index.html', playlist_name=playlist_name, tracks=tracks, playlist_url=playlist_url)

@app.route('/play', methods=['POST'])
def play():
    data = request.get_json()
    track_id = data['track_id']
    # Call the function to play the track using the track_id
    spotify_api.play_track(track_id)
    return jsonify(success=True)

@app.route('/pause', methods=['POST'])
def pause():
    data = request.get_json()
    track_id = data['track_id']
    # Call the function to pause the track using the track_id
    spotify_api.pause_track(track_id)
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True, port=5555)