import React, { useState, useEffect } from "react";
import TracksTable from "./TracksTable";
import axios from "axios";
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
  // const [gptText, setGptText] = useState("");
  // const [gptTracks, setGptTracks] = useState([]);
  const [beforeText, setBeforeText] = useState("");
  const [afterText, setAfterText] = useState("");

  // ✅ Check login status when app loads
  useEffect(() => {
    // Check if user is logged in
    fetch("/me")
      .then((res) => {
        if (!res.ok) throw new Error("Not logged in");
        return res.json();
      })
      .then((data) => {
        setUser({ name: data.user_name });
      })
      .catch(() => {
        setUser(null);
      });
  }, []);

  const handleLogin = async () => {
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
      const res = await axios.post("/confirm-playlist");
      setTracks(res.data.tracks);
      setPlaylistUrl(res.data.playlist_url);
      setStep(3); // Move to the final step
    } catch (err) {
      console.error(err);
      setError("Error creating Spotify playlist.");
    }
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      // Prevent Enter from creating a new line
      e.preventDefault();
      handleChat();
    }
  };

  return (
    <div className="App">
      <div className="header">
        <div className="app-title">Jemya | Playlist generator</div>
        <div className="login-section">
          {user ? (
            <>
              <span>👤 {user.name}</span>
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
        
      <div className="main-content">
        {step === 2 && (
          <div className="gpt-playlist-section">
            <h3>Playlist Suggestion</h3>

            {beforeText && <p>{beforeText}</p>}

            <div className="tracks">
              <TracksTable data={gptReply} />
            </div>

            {afterText && <p>{afterText}</p>}

            <button className="submit-button" onClick={handleConfirm} disabled={loading}>
              Approve & Create Playlist
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="playlist-created-section">
              <a href={playlistUrl} target="_blank" rel="noopener noreferrer">Open Playlist on Spotify</a>
            <div className="tracks">
              <h4>Tracks:</h4>
              <TracksTable data={tracks} />
            </div>
          </div>
        )}

        {error && <p className="error">{error}</p>}
      </div>

      {/* Footer with only one prompt input */}
      <div className="footer">
        <div className="prompt-container">
          <textarea
            className="prompt-input"
            rows="4"
            placeholder="Describe your mood, vibe, or activity..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyPress={handleKeyPress} // Trigger on Enter
          />
        </div>
      </div>
      </div>
  );
}

export default App;
