#!/bin/bash

export BRIDGE_SERVER_URL="https://kerong-modbus-emulator.vercel.app"
export BRIDGE_AUTH_FILE="./bridge-auth.json"

"$(dirname "$0")/run-serial-bridge.sh"
