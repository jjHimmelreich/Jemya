// frontend/src/App.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [message, setMessage] = useState('');
  const [chat, setChat] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Check if user is already logged in
    axios.get('/me').then(res => {
      setUser(res.data.user_id);
    }).catch(() => {});
  }, []);

  const handleLogin = async () => {
    const res = await axios.get('/login');
    window.location.href = res.data.auth_url;
  };

  const handleSend = async () => {
    if (!message.trim()) return;
    const newChat = [...chat, { role: 'user', content: message }];
    setChat(newChat);
    setMessage('');
    setLoading(true);

    try {
      const res = await axios.post('/generate-playlist', { prompt: message });
      const { gpt_reply, playlist_url, tracks } = res.data;

      newChat.push({ role: 'gpt', content: gpt_reply });
      newChat.push({ role: 'spotify', playlist_url, tracks });
      setChat([...newChat]);
    } catch (err) {
      console.error(err);
    }

    setLoading(false);
  };

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Spotify Playlist Chat</h1>

      {!user ? (
        <button className="bg-green-600 text-white px-4 py-2 rounded" onClick={handleLogin}>Login with Spotify</button>
      ) : (
        <>
          <div className="border p-4 h-[60vh] overflow-y-auto rounded space-y-4 mb-4">
            {chat.map((msg, i) => (
              <div key={i} className={msg.role === 'user' ? 'text-right' : 'text-left'}>
                {msg.role === 'spotify' ? (
                  <div>
                    <p className="font-semibold">🎵 Spotify Playlist:</p>
                    <a href={msg.playlist_url} target="_blank" className="text-blue-500 underline">Open Playlist</a>
                    <ul className="text-sm mt-2 list-disc ml-5">
                      {msg.tracks.map((track, i) => (
                        <li key={i}>{track.title} - {track.artist}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p>{msg.content}</p>
                )}
              </div>
            ))}
            {loading && <p className="italic text-gray-500">GPT is generating your playlist...</p>}
          </div>

          <div className="flex gap-2">
            <input
              className="border flex-1 px-4 py-2 rounded"
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Describe the kind of playlist you want..."
            />
            <button className="bg-blue-600 text-white px-4 py-2 rounded" onClick={handleSend}>Send</button>
          </div>
        </>
      )}
    </div>
  );
}