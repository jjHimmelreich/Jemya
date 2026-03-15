#!/bin/bash
# Run the FastAPI backend and React frontend together

# Kill any lingering processes on ports 5555 and 8000
echo "Checking for existing processes on ports 5555 / 8000..."
lsof -ti :5555 | xargs kill -9 2>/dev/null && echo "Killed process on :5555" || true
lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "Killed process on :8000" || true
sleep 1

# ── Backend ─────────────────────────────────────────────────────────────────

echo "🚀 Starting FastAPI backend on http://localhost:8000 ..."
# Install backend deps using the same python3.11 used by the project
python3.11 -m pip install -r backend/requirements.txt -q || true

# Verify fastapi is available before starting
python3.11 -c "import fastapi" 2>/dev/null || {
  echo "ERROR: fastapi not installed. Run: python3.11 -m pip install fastapi uvicorn[standard]"
  exit 1
}

# Start uvicorn in background
python3.11 -m uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────

echo "🎵 Starting React frontend on http://localhost:5555 ..."
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

cd ..

# ── Cleanup on exit ──────────────────────────────────────────────────────────

trap "echo '🛑 Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

echo ""
echo "✅ Jemya is running!"
echo "   Frontend → http://localhost:5555"
echo "   Backend  → http://localhost:8000"
echo "   API docs → http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

wait
