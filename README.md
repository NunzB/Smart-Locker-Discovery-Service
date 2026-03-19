# Smart Locker Discovery Service

# Overview
The **Locker Discovery Service** is a sophisticated solution designed to completely automate the physical reconstruction of an electronic locker grid. This service dynamically talks over an RS-485 Modbus RTU bus, auto-detects active lock controller boards, reads their metadata, and deterministically rebuilds a JSON layout describing every physical column, row, and compartment. 

The service provides a REST API (FastAPI) and a human-friendly interactive REPL client to query layouts, open doors, and detect hardware new boards, substitutions, or disappearances in between scans!

---

###
# Architecture & Features
###

The project is built around modular, strictly decoupled components located in `src/core`:

* **Modbus Client (`modbus.py`)**: Abstracted driver handling low-level Serial communication. Manages byte framing, CRC-16 Modbus appending, and register reads/writes.
* **Board Scanner (`scanner.py`)**: Responsible for sweeping Modbus loop addresses (1-16). When a board responds, it also reads critical metadata: Board model, Capacity (locks count), Firmware version, User Data Registers and the Lock statuses.
* **Layout Builder (`layout_builder.py`)**: Translates the raw electronics (boards) into a logical human grid (`LockerLayout`). It assigns row letters (e.g. A..Z, AA) and column numbers, combining them into explicit compartment labels (e.g. "A1", "D2").
* **Mapping Store (`mapping_store.py`)**: Persists the generated JSON layout to the filesystem (`data/locker_layout.json`). When the system reboots, it diffs the active Modbus boards against its memory to instantly detect disappeared hardware or **Replacement Boards** (restoring the previous door mapping to the new board automatically).
* **Door Service (`door_service.py`)**: Translates high-level logical commands (`open("A1")`) into explicit physical unlock bytes sent to the correct board via Modbus. It synchronously polls the hardware lock register to guarantee a physical open before returning a standard `OpenResult` success.
* **FastAPI Server (`main.py`)**: Exposes all Modbus discovery and physical Door actions over standard HTTP REST endpoints.
* **Interactive Clients (`api_repl.py` & `main_repl.py`)**: Highly useful CLI interfaces that allow operators to execute commands (send `h` or `help` to see available commands) effortlessly.

---


###
# Quick Start (Docker Sandbox)
###
The fastest and most stable way to run the service is through the completely isolated Docker environment. This bundles the required `socat` virtual serial bridge directly with the FastAPI app, meaning you don't have to install any system packages.

### Requirements:
* **Docker** & **Docker Compose**

### Step 1: Insert Auth Credentials for the Bridge
Rename the file `aux/bridge-auth.json.example` to `aux/bridge-auth.json` and insert the auth credentials for the bridge.

### Step 2: Launch the API Server
Make sure to have docker running beforehand. Run the following command at the root of the project to build the image and bring the server up:
```bash
docker compose up --build
```
*(The start script in start_service.sh will clone the bridge_server_client repo and launch the bridge exposing it on `/tmp/serial_bridge` inside the container. Then it will launch the FastAPI app in `main.py` and expose the server on port `8000`)*.

### Step 3: Launch the Interactive Client
Instead of manually typing REST requests, use the provided interactive REPL API client. Run the REPL inside the Docker Container so you don't have to install any system packages. 

```bash
docker compose exec -it locker-api ./start_api_repl.sh
```

---

###
# Execution on a Linux Host
###
If you prefer to run the architecture natively on your host machine without Docker, we have provided direct execution scripts. 

### Local Requirements:
* **Linux OS** 
* **Python 3.11+**
* `socat` (Install via `sudo apt-get install socat`)
* `git`

## 1st Option 
### Launching the Backend Service Natively
Run the service script. It will automatically initialize a sandboxed `.venv`, fetch Python dependencies, download the serial bridge repo, and boot the FastAPI server. 
*(Note: Keep this terminal window open to keep the server alive!)*
```bash
./start_service.sh
```

### Testing the Service (API Client)
In a second terminal window, run the native API client to talk to the local background server:
```bash
./start_api_repl.sh
```

## 2nd Option
### Standalone Mode - REPL with Direct Module access 
Make sure to have the bridge running before running the REPL. You can run the bridge manually with (to have the serial bridge client repo you need to run the `start_service.sh` once):
```bash
./serial-bridge-client/run_custom_bridge.sh
```

If you want to debug, test new features, or bypass the HTTP API entirely to direct Modbus communication via the bridge on `/tmp/serial_bridge`, you can run the direct, uncoupled REPL:
```bash
./start_standalone_repl.sh
```
