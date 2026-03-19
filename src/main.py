import logging
import argparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os

from core.modbus import ModbusClient
from core.scanner import BoardScanner
from core.layout_builder import LayoutBuilder
from core.mapping_store import MappingStore
from core.door_service import DoorService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Locker Discovery Service")

class State:
    client = None
    scanner = None
    builder = None
    store = None
    door_service = None
    last_boards = []
    last_layout = None

state = State()

class ResetRequest(BaseModel):
    address: int

class OpenRequest(BaseModel):
    label: str

@app.on_event("startup")
def startup_event():
    # Use environment variables with fallbacks to defaults
    port = os.getenv("MODBUS_PORT", "/tmp/serial_bridge")
    baudrate = int(os.getenv("MODBUS_BAUDRATE", 19200))
    layout_file = os.getenv("LAYOUT_FILE", "data/locker_layout.json")
    boards_file = os.getenv("BOARDS_FILE", "data/locker_boards.json")

    logger.info(f"Initializing Service on port={port}, baudrate={baudrate}")

    state.client = ModbusClient(port=port, baudrate=baudrate)
    state.scanner = BoardScanner(state.client)
    state.builder = LayoutBuilder()
    state.store = MappingStore(layout_filepath=layout_file, boards_filepath=boards_file)
    state.door_service = DoorService(state.client, state.scanner, state.store)
    
    try:
        state.client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Modbus client on startup: {e}")

@app.on_event("shutdown")
def shutdown_event():
    if state.client:
        state.client.disconnect()

@app.post("/scan")
def trigger_scan():
    """Scans the bus and updates state memory boards."""
    state.last_boards = state.scanner.scan_bus()
    state.last_layout = state.builder.build(state.last_boards)
    # success always true, if read failed or no response is found, it will return empty list
    return {
        "status": "success",
        "boards": state.last_boards
    }

# @app.post("/layout")
# def build_layout():
#     """Builds layout from state memory boards."""
#     state.last_layout = state.builder.build(state.last_boards)
#     return {"status": "success", "layout": state.last_layout}

@app.get("/compare")
def compare_data():
    """Compares state memory boards with .json file stored state."""
    if not state.last_layout:
        raise HTTPException(status_code=400, detail="Build layout first")
    new_boards, disappeared = state.store.compare_with_stored_data(state.last_boards, state.last_layout)
    return {
        "new_boards": new_boards,
        "disappeared_boards": disappeared
    }

@app.post("/update")
def update_store():
    """Updates .json file stored layout/boards from state."""
    if not state.last_layout:
        raise HTTPException(status_code=400, detail="Build layout first")
    new_boards, disappeared = state.store.update_from_scan(state.last_boards, state.last_layout)
    
    # Write 0xABCD user data register to the new boards (so that they stop being identified as new boards)
    status = "success"
    message = ""
    for board_data in new_boards:
        print(f"Writing to User Data register of board on addr {board_data['board'].address} the value 0xABCD")
        res = state.client.write_single_register(board_data['board'].address, 0x0070, 0xABCD)
        if not res:
            status = "failed" 
            message += f"Failed to write user data register to board {board.address}\n"
    return {
        "status": status,
        "new_boards": new_boards,
        "disappeared_boards": disappeared,
        "msg": message
    }

@app.post("/reset_custom_user_data")
def reset_custom_user_data(req: ResetRequest):
    print(f"Received address {req.address}")
    """Resets the user data register of a specific board to 0x0000."""
    res = state.client.write_single_register(req.address, 0x0070, 0x0000)
    if not res:
        logger.error(f"Failed to write user data register to board {req.address}")
        raise HTTPException(status_code=500, detail=f"Failed to reset board {req.address}")
    return {"status": "success"}

@app.get("/boards")
def get_memory_boards():
    """Returns the currently scanned in-memory boards."""
    return {"boards": state.last_boards}

@app.get("/layout")
def get_memory_layout():
    """Returns the currently built in-memory layout."""
    return {"boards": state.last_boards, "layout": state.last_layout}

@app.get("/stored_boards")
def get_stored_boards():
    """Returns the currently stored boards."""
    return {"boards": state.store.boards}

@app.get("/stored_layout")
def get_stored_layout():
    """Returns the currently stored layout."""
    return {"boards": state.store.boards, "layout": state.store.layout}

@app.post("/open")
def open_door(req: OpenRequest):
    """Opens a compartment by its label (e.g., 'A1')."""
    result = state.door_service.open(req.label)
    return {"status": result.name, "label": req.label}

@app.post("/close")
def close_door(req: OpenRequest):
    """Closes a compartment logically if supported."""
    result = state.door_service.close(req.label)
    return {"status": result.name, "label": req.label}

@app.post("/dummy")
def add_dummy_boards():
    """Adds dummy boards to in-memory state for testing."""
    if len(state.last_boards) > 0:
        import copy
        b2 = copy.deepcopy(state.last_boards[0])
        b2.address = 2
        state.last_boards.append(b2)
        b3 = copy.deepcopy(state.last_boards[0])
        b3.address = 3
        state.last_boards.append(b3)
        b4 = copy.deepcopy(state.last_boards[0])
        b4.address = 4
        b4.config.user_data[0] = 0xABCD
        state.last_boards.append(b4)
        return {"status": "success", "boards": state.last_boards}
    raise HTTPException(status_code=400, detail="Failed to add dummy boards. No boards to copy.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Locker Discovery Service")
    parser.add_argument("--port", default="/tmp/serial_bridge", help="Serial port (default: /tmp/serial_bridge)")
    parser.add_argument("--baudrate", type=int, default=19200, help="Baudrate (default: 19200)")
    parser.add_argument("--layout", default="data/locker_layout.json", help="Persistent layout file path")
    parser.add_argument("--boards", default="data/locker_boards.json", help="Persistent boards file path")
    args, _ = parser.parse_known_args()

    os.environ["MODBUS_PORT"] = args.port
    os.environ["MODBUS_BAUDRATE"] = str(args.baudrate)
    os.environ["LAYOUT_FILE"] = args.layout
    os.environ["BOARDS_FILE"] = args.boards

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

