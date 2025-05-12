import React from "react";

const NewPlaylistPrompt = ({ playlistName, setPlaylistName, onCreate, onCancel }) => {
  return (
    <div className="create-playlist-prompt">
      <h3>Playlist name</h3>
       <input
        type="text"
        value={playlistName}
        onChange={(e) => setPlaylistName(e.target.value)}
        placeholder="Enter a playlist name..."
        className="create-playlist-input"
      />
        <div className="create-playlist-buttons">
            <div className="side-menu-button" onClick={onCreate}>
            Create
            </div>

            <div className="side-menu-button" onClick={onCancel}>
            Cancel
            </div>
        </div> 
    </div>
  );
};

export default NewPlaylistPrompt;
