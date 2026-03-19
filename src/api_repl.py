import urllib.request
import urllib.error
import json
from core.utils import print_layout_matrix
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger()

BASE_URL = "http://localhost:8000"

def _request(method, endpoint, data=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, data=data) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        try:
            error_msg = json.loads(e.read().decode()).get("detail", e.reason)
        except Exception:
            error_msg = e.reason
        print(f"API Error ({url}): {e.code} - {error_msg}")
        return None
    except urllib.error.URLError as e:
        print(f"API Error ({url}): {e}")
        return None
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return None



def start_repl():
    """
    An interactive CLI client that communicates entirely over the REST HTTP API.
    Unlike 'main repl.py', this does NOT talk to the hardware directly. It acts as a 
    mock frontend
    """
    print("API Interactive Shell. Type 'help' or 'h' for commands.")
    print(f"Connecting to {BASE_URL}...")
    
    while True:
        try:
            cmd = input("api_client> ").strip().split()
            if not cmd: continue
            action = cmd[0].lower()
            
            if action in ("exit", "quit", "q"):
                break

            elif action in ("scan", "s"):
                print("Scanning bus via API, please wait...")
                res = _request("POST", "/scan")
                if res and res.get("status") == "success":
                    # print(json.dumps(res, indent=2))
                    boards = res.get("boards", [])
                    logger.info(f"Scan complete. Found {len(boards)} boards. Use 'sb' to show boards or 'sl' to show layout.")
               
            elif action in ("compare", "c"):
                res = _request("GET", "/compare")

                if res:
                    new_boards = res.get("new_boards", [])
                    disappeared_boards = res.get("disappeared_boards", [])
                    # 3. Log differences
                    logger.info("--- Comparison from state memory to persistent storage (.json)---")
                    if new_boards or disappeared_boards:
                        for b in new_boards:
                            if b['substitution']:
                                logger.info(f"Substitution Board on addr {b['board']['address']} (Capacity: {b['board']['capacity']})")
                            else:
                                logger.info(f"New Board on addr {b['board']['address']} (Capacity: {b['board']['capacity']})")
                        for b in disappeared_boards:
                            logger.info(f"Board vanished on addr {b['address']} (Capacity: {b['capacity']})")
                    logger.info("------------------------------------")

            elif action in ("update", "u"):
                res = _request("POST", "/update")
                if res:
                    new_boards = res.get("new_boards", [])
                    disappeared_boards = res.get("disappeared_boards", [])
                    # 3. Log differences
                    logger.info("--- Mapping Store Update Summary ---")
                    if new_boards or disappeared_boards:
                        for b in new_boards:
                            if b['substitution']:
                                logger.info(f"Substitution Board on addr {b['board']['address']} (Capacity: {b['board']['capacity']})")
                            else:
                                logger.info(f"New Board on addr {b['board']['address']} (Capacity: {b['board']['capacity']})")
                        for b in disappeared_boards:
                            logger.info(f"Board vanished on addr {b['address']} (Capacity: {b['capacity']})")
                    logger.info("------------------------------------")

                    if res.get("status") == "success":
                        logger.info("Update successful.")
                    else:
                        logger.error(f"Failed to update. Message: {res.get('message')}")

            elif action in ("reset", "r"):
                if len(cmd) < 2: 
                    print("Usage: reset | r <address>")
                    continue
                address = int(cmd[1])
                res = _request("POST", "/reset_custom_user_data", {"address": address})
                if res:
                    print(json.dumps(res, indent=2))

            elif action in ("show_boards", "sb"):
                res = _request("GET", "/boards")
                if res:
                    boards = res.get("boards", [])
                    logger.info(f"Boards in server state: {len(boards)} boards. Boards: {boards}")
               
            elif action in ("show_layout", "sl"):
                res = _request("GET", "/layout")
                if res:
                    layout = res.get("layout")
                    boards = res.get("boards", [])
                    print(json.dumps((layout), indent=2))
                    print_layout_matrix(boards, layout)

            elif action in ("show_stored_boards", "ssb"):
                res = _request("GET", "/stored_boards")
                if res:
                    boards = res.get("boards", [])
                    logger.info(f"Boards in persistent storage: {len(boards)} boards. Boards: {boards}")

            elif action in ("show_stored_layout", "ssl"):
                res = _request("GET", "/stored_layout")
                if res:
                    layout = res.get("layout")
                    boards = res.get("boards", [])
                    print(json.dumps((layout), indent=2))
                    print_layout_matrix(boards, layout)
                
            elif action in ("dummy", "d"):
                res = _request("POST", "/dummy")
                if res and res.get("status") == "success":
                    logger.info(f"Added dummy boards.")

            elif action in ("open", "o"):
                if len(cmd) < 2:
                    print("Usage: open <label> (e.g., open A1)")
                    continue
                label = cmd[1].upper()
                print(f"Opening compartment {label} via API...")
                res = _request("POST", "/open", {"label": label})
                if res:
                    print(json.dumps(res, indent=2))
            elif action in ("close", "cl"):
                if len(cmd) < 2:
                    print("Usage: close <label> (e.g., close A1)")
                    continue
                label = cmd[1].upper()
                print(f"Closing compartment {label} via API...")
                res = _request("POST", "/close", {"label": label})
                if res:
                    print(json.dumps(res, indent=2))
            elif action in ("help", "h"):
                print("Commands:")
                print("  s / scan                 - Scan bus and update in-memory boards and layout")
                print("  c / compare              - Compare in-memory boards and layout with stored (No changes to files)")
                print("  u / update               - Update stored layout/boards from in-memory (Changes files)")
                print("  r / reset <address>      - Reset custom user data register of a specific board")
                print("  o / open <label>         - Open compartment (e.g. open A1)")
                print("  cl / close <label>       - Close compartment logically")
                print("  sb / show_boards         - Show boards in memory")
                print("  sl / show_layout         - Show layout in memory")
                print("  ssb / show_stored_boards - Show stored boards (.json)")
                print("  ssl / show_stored_layout - Show stored layout (.json)")
                print("  d / dummy                - Add dummy boards to memory")
                print("  q / quit / exit          - Exit shell")
            else:
                print("Unknown command. Type 'help' for available commands.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except EOFError:
            print("\nExiting...")
            break

if __name__ == "__main__":
    start_repl()
