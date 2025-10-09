#!/bin/bash

# Detect available Python 3.11 version
if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD="python3.11"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    echo "Error: Python 3 not found. Please install Python 3.11+"
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Add user Python bin to PATH if needed
export PATH="$HOME/Library/Python/3.11/bin:$PATH"

# Check for and close any existing processes on port 5555
echo "Checking for existing processes on port 5555..."
EXISTING_PID=$(lsof -ti :5555)
if [ ! -z "$EXISTING_PID" ]; then
    echo "Found existing process(es) on port 5555: $EXISTING_PID"
    echo "Closing existing process(es)..."
    kill $EXISTING_PID
    sleep 2
    # Check if process is still running and force kill if necessary
    STILL_RUNNING=$(lsof -ti :5555)
    if [ ! -z "$STILL_RUNNING" ]; then
        echo "Force killing stubborn process(es): $STILL_RUNNING"
        kill -9 $STILL_RUNNING
        sleep 1
    fi
    echo "Port 5555 is now free."
else
    echo "Port 5555 is already free."
fi

# Install required packages if needed
echo "Installing required packages..."
$PYTHON_CMD -m pip install --user streamlit spotipy openai

# Run the streamlit app
echo "Starting Streamlit app..."
streamlit run app.py --server.port=5555