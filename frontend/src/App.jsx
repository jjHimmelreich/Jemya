import React, { useState, useEffect } from "react";
import TracksTable from "./TracksTable";
import NewPlaylistPrompt from "./NewPlaylistPrompt";

import axios from "axios";
import "./normal.css";
import "./App.css";
import { extractJsonAndText } from "./utils";

function App() {

  const [prompt, setPrompt] = useState("");
  const [gptReply, setGptReply] = useState("");
  const [tracks, setTracks] = useState([]);
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [user, setUser] = useState(null);
  const [beforeText, setBeforeText] = useState("");
  const [afterText, setAfterText] = useState("");
  const [showPromptInput, setShowPromptInput] = useState(false);
  const [playlistName, setPlaylistName] = useState("");


  useEffect(() => {
    fetch("/me")
      .then((res) => { if (!res.ok) throw new Error("Not logged in"); return res.json();})
      .then((data) => {
        setUser({ name: data.user_name });
        getPlaylists(); // Call after confirming the user is logged in
      })
      .catch(() => { setUser(null); });
  }, []);

  function getPlaylists() { 
    fetch("/playlists") // Get list of user playlists
      .then(res => res.json())
      .then(data => console.log(data))
  }

  const handleLogin = () => {
    window.location.href = "http://localhost:5555/login";
  };

  const handleLogout = async () => {
    try {
      await axios.post("/logout");
      setUser(null);
      setStep(1);
      setPrompt("");
      setGptReply("");
      setTracks([]);
      setPlaylistUrl("");
      setBeforeText("");
      setAfterText("");
    } catch (err) {
      console.error("Logout failed", err);
    }
  };

  const handleChat = async () => {
    if (prompt.trim() === "") return;

    setLoading(true);
    setError("");
    setPrompt("")
    try {
      const res = await axios.post("/chat", { prompt }, { withCredentials: true });
      const { beforeText, afterText, data } = extractJsonAndText(res.data.result);

      setBeforeText(beforeText);
      setAfterText(afterText);
      setGptReply(data);
      setStep(2);
    } catch (err) {
      console.error(err);
      setError("Error generating playlist idea.");
    }
    setLoading(false);
  };

  const handleConfirm = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await axios.post("/playlist"); // Confirm suggested playlist
      setTracks(res.data.tracks);
      setPlaylistUrl(res.data.playlist_url);
      setStep(3);
    } catch (err) {
      console.error(err);
      setError("Error creating Spotify playlist.");
    }
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleChat();
    }
  };

  const handleNewPlaylist = async () => { 
    console.log('Creating new playlist');
    try {
      const res = await axios.put("/playlist", {"name": playlistName}); // Creaate new empty playlist
      setTracks(res.data.tracks);
      setPlaylistUrl(res.data.playlist_url);
      setStep(3);
    } catch (err) {
      console.error(err);
      setError("Error creating Spotify playlist.");
    }
  }

  const handleCancel = () => {
    setShowPromptInput(false);
  };
  
  return (
    <div className="App">

      {/* Side menu container */}
      <aside className="sidemenu">
        <div className="side-menu-button" onClick={() => setShowPromptInput(true)}>
          <span>+</span>
          New Playlist
          </div>
      </aside>
      
      <section className="chatbox">
        
          {showPromptInput && (
            <div className="modal-overlay">
              <div className="modal-content">
              <NewPlaylistPrompt
                playlistName={playlistName}
                setPlaylistName={setPlaylistName}
                onCreate={handleNewPlaylist}
                onCancel={handleCancel}
              />
              </div>
            </div>
          )}


            <div className="header">
              <div className="app-title">Jemya | Playlist generator</div>
              <div className="login-section">
                {user ? (
                  <>
                    <span>{user.name}</span>
                    <button className="login-btn" onClick={handleLogout}>
                      Logout
                    </button>
                  </>
                ) : (
                  <button className="login-btn" onClick={handleLogin}>
                    Login with Spotify
                  </button>
                )}
              </div>
            </div>

        {step === 2 && (
          <div className="gpt-playlist-section">
            <h3>Playlist Suggestion</h3>
            {beforeText && <p>{beforeText}</p>}
            {gptReply && (
              <div className="tracks">
                <TracksTable data={gptReply} />
              </div>
            )}
            {afterText && <p>{afterText}</p>}

            {gptReply && (
              <button className="submit-button" onClick={handleConfirm} disabled={loading}>
                Approve & Create Playlist
              </button>
            )}
              </div>
            
            )}

            {step === 3 && (
              <div className="playlist-created-section">
                <a href={playlistUrl} target="_blank" rel="noopener noreferrer">
                  Open Playlist on Spotify
                </a>
                <div className="tracks">
                  <h4>Tracks:</h4>
                  <TracksTable data={tracks} />
                </div>
              </div>
            )}

            {error && <p className="error">{error}</p>}

        <div className="prompt-container">
          <textarea className="prompt-input-textarea" rows="4" placeholder="Describe your mood, vibe, or activity..." value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyPress={handleKeyPress} />
        </div>
        
      </section>
    </div>
  );
}

export default App;
