#!/bin/bash

# set venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
    echo "Installing dependencies in venv..."
    .venv/bin/pip install -r requirements.txt
fi

echo "Activating virtual environment..."
source .venv/bin/activate

cd src
echo "Starting REPL standalone app..."

# Run the uvicorn server synchronously so the bash script waits for it to finish
python main_repl.py
