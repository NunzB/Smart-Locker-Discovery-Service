import argparse
import sys
import logging
from core.modbus import ModbusClient
from core.scanner import BoardScanner
from core.layout_builder import LayoutBuilder
from core.mapping_store import MappingStore
from core.door_service import DoorService
# from models import OpenResult
import json
from dataclasses import asdict
from core.utils import print_layout_matrix

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger()

# def print_layout_matrix(boards, layout):
    # if not layout.columns:
    #     print("Empty layout")
    #     return

    # max_rows = max((len(col.rows) for col in layout.columns), default=0)
    
    # # Header
    # cell_width = 18
    # header_cells = [f"Board {i+1} (Addr {boards[i].address})".center(cell_width) for i in range(len(layout.columns))]
    # header_row = " | ".join(header_cells)
    # print("\n" + header_row)
    # print("-" * len(header_row))
    
    # # Rows
    # for r in range(max_rows):
    #     row_cells = []
    #     for col in layout.columns:
    #         if r < len(col.rows) and col.rows[r].compartments:
    #             comps_str = []
    #             for comp in col.rows[r].compartments:
    #                 status_char = "X" if comp.lockStatus else "c"
    #                 comps_str.append(f"{comp.label}({status_char})")
    #             label = " ".join(comps_str)
    #             row_cells.append(label.center(cell_width))
    #         else:
    #             row_cells.append(" " * cell_width)
    #     print(" | ".join(row_cells))
    # print()


def run_repl(client: ModbusClient, scanner: BoardScanner, builder: LayoutBuilder, store: MappingStore, door_service: DoorService):
    """
    An interactive shell designed for easy testing. 
    It bypasses the REST API entirely, communicating straight down to the 
    core domain services.
    """
    print("Interactive Shell. Type 'help' or 'h' for commands.")

    boards = []
    layout = []

    while True:
        try:
            # sys.stdout.write is safer in some environments than input() if stdout is weird, but input() is fine.
            cmd = input("locker_layout_builder> ").strip().split()
            if not cmd:
                continue
                
            action = cmd[0].lower()
            
            if action in ("exit", "quit", "q"):
                break
            elif action in ("scan", "s"):
                boards = scanner.scan_bus()
                logger.info(f"Scan complete. Found {len(boards)} boards. Boards: {boards}")

            elif action in ("layout", "l"):
                layout = builder.build(boards)
                print(json.dumps(asdict(layout), indent=2))
                logger.info("Layout Matrix (X=open, c=closed):")
                print_layout_matrix(boards, layout)

            elif action in ("compare", "c"):
                store.compare_with_stored_data(boards, layout)

            elif action in ("update", "u"):
                new_boards_list, disappeared_boards_list = store.update_from_scan(boards, layout)
                for board_data in new_boards_list:
                    logger.info(f"Writing to User Data register of board on addr {board_data['board'].address} the value 0xABCD")
                    res = client.write_single_register(board_data['board'].address, 0x0070, 0xABCD)
                    if not res:
                        logger.error(f"Failed to write user data register to board {board_data['board'].address}")

            elif action in ("reset", "r"):
                if len(cmd) < 2: 
                    print("Usage: reset | r <address>")
                    continue
                address = int(cmd[1])
                res = client.write_single_register(address, 0x0070, 0x0000)
                if not res:
                    logger.error(f"Failed to write user data register to board {address}")
                    
            elif action in ("show_boards", "sb"):
                logger.info(f"Num boards: {len(boards)}. Boards: {boards}")
 
            elif action in ("show_layout", "sl"):
                logger.info(f"Layout: {layout}")
                if layout:
                    logger.info(f"Layout Matrix (o=open, X=closed):")
                    print_layout_matrix(boards, layout)

            elif action in ("show_stored_boards", "ssb"):
                logger.info(f"Num boards: {len(store.boards)}. Boards: {store.boards}")

            elif action in ("show_stored_layout", "ssl"):
                logger.info(f"Layout: {store.layout}")
                logger.info(f"Layout Matrix (o=open, X=closed):")
                print_layout_matrix(store.boards, store.layout)

            elif action in ("dummy", "d"):
                # Add dummy boards to in-memory boards list for testing purposes
                if len(boards) > 0:
                    import copy
                    b2 = copy.deepcopy(boards[0])
                    b2.address = 2
                    boards.append(b2)
                    b3 = copy.deepcopy(boards[0])
                    b3.address = 3
                    boards.append(b3)
                    b4 = copy.deepcopy(boards[0])
                    b4.address = 4
                    b4.config.user_data[0] = 0xABCD
                    boards.append(b4)

                    logger.info(f"Added dummy boards.")
                else:
                    logger.warning("Need at least 1 board to use as copy for dummy boards.")

            elif action in ("open", "o"):
                if len(cmd) < 2:
                    print("Usage: open <label> (e.g., open A1)")
                    continue
                label = cmd[1].upper()
                result = door_service.open(label)
                print(f"Result: {result.name}")

            elif action in ("close", "cl"):
                if len(cmd) < 2:
                    print("Usage: close <label> (e.g., close A1)")
                    continue
                label = cmd[1].upper()
                result = door_service.close(label)
                print(f"Result: {result.name}")

            elif action in ("help", "h"):
                print("Commands:")
                print("  s / scan                 - Scan bus and update in-memory boards")
                print("  l / layout               - Build layout from in-memory boards")
                print("  c / compare              - Compare in-memory boards and layout with stored boards and layout")
                print("  u / update               - Update stored layout and boards from in-memory boards and layout")
                print("  o / open                 - Open compartment (e.g. open A1 | o A1)")
                print("  sb / show_boards         - Show boards in program memory")
                print("  sl / show_layout         - Show layout in program memory")
                print("  ssb / show_stored_boards - Show boards in .json file")
                print("  ssl / show_stored_layout - Show layout in .json file")
                print("  d / dummy                - Add dummy boards to in-memory boards list for testing purposes")
                
                print("  q / quit / exit          - Exit shell")
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except EOFError:
            print("\nExiting...")
            break
        except Exception as e:
            logger.error(f"Error executing command: {e}")


def main():
    parser = argparse.ArgumentParser(description="Dynamic Locker Layout Service")
    parser.add_argument("--port", default="/tmp/serial_bridge", help="Serial port (default: /tmp/serial_bridge)")
    parser.add_argument("--baudrate", type=int, default=19200, help="Baudrate (default: 19200)")
    parser.add_argument("--layout", default="data/locker_layout.json", help="Persistent layout file path")
    parser.add_argument("--boards", default="data/locker_boards.json", help="Persistent boards file path")
    args = parser.parse_args()

    client = ModbusClient(port=args.port, baudrate=args.baudrate)
    scanner = BoardScanner(client)
    builder = LayoutBuilder()
    store = MappingStore(layout_filepath=args.layout, boards_filepath=args.boards)
    door_service = DoorService(client, scanner, store)


    try:
        client.connect()
    except Exception as e:
        logger.error(f"Could not connect to Serial Bridge Client: {e}")
        sys.exit(1)

    # boards = scanner.scan_bus()
    # logger.info(f"Scan complete. Found {len(boards)} boards.")
    # logger.info(f"Boards: {boards}")

    # # Add dummy boards
    # if len(boards) > 0:
    #     import copy
    #     b2 = copy.deepcopy(boards[0])
    #     b2.address = 2
    #     boards.append(b2)
        
    #     b3 = copy.deepcopy(boards[0])
    #     b3.address = 3
    #     boards.append(b3)
        


    # layout = builder.build(boards)
    # logger.info("Layout Matrix (o=open, X=closed):")
    # print_layout_matrix(boards, layout)


    # store.update_from_scan(boards, layout)

    # Initial scan to load/reconstruct layout
    # logger.info("Performing initial scan...")
    # boards = scanner.scan_bus()
    # logger.info(f"Found {len(boards)} boards. Updating layout...")
    # store.update_from_scan(boards, builder)

    # Run the interactive shell
    run_repl(client, scanner, builder, store, door_service)
    
    client.disconnect()

if __name__ == "__main__":
    main()
