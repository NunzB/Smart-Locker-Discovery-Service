#!/bin/bash
set -e

# 1. Clone the bridge client
if [ ! -d "serial-bridge-client" ]; then
    echo "Cloning Bloq.it serial-bridge-client..."
    git clone https://github.com/brunofbloq/serial-bridge-client.git

    # Extract the linux bridge binary
    tar -xzf ./serial-bridge-client/bin/serial-bridge-v0.1.0-linux-x64.tar.gz -C ./serial-bridge-client/bin/linux-x64/
    mv ./serial-bridge-client/bin/linux-x64/serial_bridge_client.dist/* ./serial-bridge-client/bin/linux-x64/
    rm -rf ./serial-bridge-client/bin/linux-x64/serial_bridge_client.dist/

    #Make scripts executable
    chmod +x ./serial-bridge-client/run-serial-bridge.sh
    chmod +x ./serial-bridge-client/bin/linux-x64/serial_bridge

    
else
    echo "serial-bridge-client already exists."
fi

# 2. Check if auth file exists in bridge client, if not copy from aux
if [ ! -d "serial-bridge-client/bridge-auth.json" ]; then
    cp ./aux/bridge-auth.json ./serial-bridge-client/bridge-auth.json
    cp ./aux/run_custom_bridge.sh ./serial-bridge-client/run_custom_bridge.sh

    #Make scripts executable
    chmod +x ./serial-bridge-client/run_custom_bridge.sh
    chmod +x ./serial-bridge-client/run-serial-bridge.sh
    chmod +x ./serial-bridge-client/bin/linux-x64/serial_bridge
fi

# 3. Start serial bridge client in background
echo "Starting serial bridge..."
# Enter the serial-bridge-client directory to reliably pick up bridge-auth.json and relative paths
cd ./serial-bridge-client

# Runs bridge in background. To kill it: pkill -f "serial_bridge|socat" 
./run_custom_bridge.sh &


echo "Waiting for /tmp/serial_bridge to be created..."
TIMEOUT=30
while [ ! -e /tmp/serial_bridge ]; do
  sleep 1
  TIMEOUT=$((TIMEOUT-1))
  if [ "$TIMEOUT" -le 0 ]; then
    echo "ERROR: Timed out waiting for /tmp/serial_bridge. Ensure auth is correct"
    exit 1
  fi
done
echo "/tmp/serial_bridge is ready."

cd ..

#log current directory
echo "Current directory: $(pwd)"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
    echo "Installing dependencies in venv..."
    .venv/bin/pip install -r requirements.txt
fi

echo "Activating virtual environment..."
source .venv/bin/activate


cd src
echo "Starting FastAPI app..."

# Define cleanup function to kill background processes
cleanup() {
    echo "Closing serial bridge..."
    pkill -f "serial_bridge|socat" || true
}

# Trap the script exit or interrupt to automatically run the cleanup
trap cleanup EXIT INT

# Run the uvicorn server synchronously so the bash script waits for it to finish
python main.py
