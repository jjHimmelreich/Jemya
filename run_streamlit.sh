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

# Install required packages if needed
echo "Installing required packages..."
$PYTHON_CMD -m pip install --user streamlit spotipy openai

# Run the streamlit app
echo "Starting Streamlit app..."
streamlit run app.py --server.port=5555