#!/bin/bash
# Run the FastAPI backend and React frontend together

# ── Backend ─────────────────────────────────────────────────────────────────

echo "🚀 Starting FastAPI backend on http://localhost:8000 ..."
# Install backend deps if needed
pip install -r backend/requirements.txt --quiet

# Start uvicorn in background
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────

echo "🎵 Starting React frontend on http://localhost:5173 ..."
cd frontend

# Copy example env if .env.local doesn't exist
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "Created frontend/.env.local from .env.example"
fi

npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

cd ..

# ── Cleanup on exit ──────────────────────────────────────────────────────────

trap "echo '🛑 Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

echo ""
echo "✅ Jemya is running!"
echo "   Frontend → http://localhost:5173"
echo "   Backend  → http://localhost:8000"
echo "   API docs → http://localhost:8000/docs"
echo ""
echo "⚠️  IMPORTANT: Update your Spotify app redirect URI to: http://localhost:5173"
echo "   Spotify Dashboard: https://developer.spotify.com/dashboard"
echo ""
echo "Press Ctrl+C to stop both servers."

wait
