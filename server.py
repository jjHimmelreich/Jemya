from flask import Flask, request, render_template
import spotify_api

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    tracks = None
    playlist_name = None
    playlist_url = None
    if request.method == 'POST':
        playlist_url = request.form['playlist_url']
        # Use the mock_process_playlist function for now
        playlist_name, tracks = spotify_api.process_playlist(playlist_url)
    return render_template('index.html', 
                           playlist_name=playlist_name, 
                           playlist_url=playlist_url,
                           tracks=tracks)

if __name__ == '__main__':
    app.run(debug=True)