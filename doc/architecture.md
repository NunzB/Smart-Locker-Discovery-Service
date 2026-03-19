Architecture and Components
**Before writing any code**, produce a short document (can be a diagram + bullet points) that answers:
> There is no single correct answer.
> The proposal is evaluated on clarity of boundaries and completeness of reasoning

# 0. Data from Challenge
 - Physical Lockers are a matrix of compartments (A...Z rows x 1...N columns). The compartments are labeled row_label + column_number ("A1", "B1" ... "Z1", "AA1" ... "AZ1" ... "BA1" ... "BZ1" ... "CA1" ...)
 - Let's assume each column has a lock controller, with a unique device address, connected to a RS-485 Modbus RTU bus. 
 - Each lock controller drives N locks (e.g. 48, 24, 16). 
 - Let's assume a lock is an item on specific row x column, that belongs to that compartment.


# 1. What are the components and what does each one own?

## 1.1. Modbus Client
- The component that talks to the serial port from the bridge-server-client. 
- It should be able to connect, disconnect, send data and receive data. 
- Should have methods to read and write registers. 
- Should append CRC to every request and check CRC of every response.

## 1.2. Bus Scanner
- Component that scans the bus for available boards.

- Method to scan the bus: loops over the addresses 1 to 16. For each address, should read the Board ID register (0x000F). It has a custom blacklist that allows the user to set addresses not to scan. 
    - If a board does not respond, it is considered absent. 
    - If the read failed type is not identified (models registered according to table in appendix 3 of the challenge description), defaults capacity to 48 and log a warning.
    - If the response is valid, gets the model (High Byte) and max capacity (Low Byte) from the response data. 

- Then, get all the available info for that board: 
    - Firmware Version (reg 0x00F5) - High byte = SW version, Low byte = HW version
    - Voltage (reg 0x00F7) - mV units
    - Baud Rate (reg 0x00F2) - 0 = 9600, 1 = 19200
    - Lock Status (reg 0x0000) - N bits, 1 = closed, 0 = open. We read the number of bits based on the capacity of the board.
    - IR Counter (reg 0x0090 - 0x0093) - 4 x 16-bit registers for port (1-4). 
    - Opening Time (reg 0x00F0) - Multiply register value by 10 to get the value in ms.
    - LED Time (reg 0x00F8) - Unit seconds. Default 5s.
    - User Data (reg 0x0070 - 0x0079) - Registers available for the app to use.
    
### Data Structures
- class BoardInfo:
    - address: int                        # Stores address of the board on the - bus
    - model: Dict[int, str]               # Stores (key = model id, value = model name)
    - capacity: int                       # Stores max capacity 
    - config: BoardConfig                 # Stores config registers data
    - counters: BoardCounters             # Stores counter registers data
    - status: List[bool]                  # Stores lock status (index = lock id, value = True if close, False if open)

- class BoardConfig:
    - sw_version: int             # High byte of reg 0x00F5           
    - fw_version: int             # Low byte of reg 0x00F5
    - mV: int                     # Voltage in mV
    - baudrate: int               # 9600 or 19200
    - opening_time: int           # in ms
    - led_time: int               # in seconds
    - user_data: List[int]        # 10 x 16-bit registers 

- class BoardCounters:
    - IRports: List[int]          # 4 x 16-bit registers for port (1-4).

## 1.3. Layout Builder
- Component that builds the layout of the locker from a list of BoardInfo objects. In the challenge it is not clear how to retrieve the necessary information to figure out the open direction and size of each lock. However, in the json door mapping example it is possible to see that the open direction and size are stored in the mapping. 
- 2 different approaches:
    - We simplify and build a 2D data structure, where each column is a BoardInfo object and each row is a lock. This means each row is a compartment. 
    - We build a 3D data structure (columns, rows and depth). 
        - Each column is a BoardInfo object.
        - Each row is a list of compartments 
        - The number of rows of each column may not correspond to the number of locks for that board.
        
- In my proposed solution I go with the previous option 2, but with some assumptions:
    - I assume default values for the openDirection and size properties of each compartment.
    - I assume a single compartment per row. This means the number of rows is equal to the capacity of the board.

- Method to build the layout from scratch: 
    - It receives a list of BoardInfo objects and produces a 3D List (columns x rows x depth). The depth is always 1. 
    - Using a list of boards sorted by address, for each board it adds a column. For each lock in that board (based on the max capacity of the board), it adds a row with a single compartment.
    - The compartment info is: 
        - label: - RowLabel + ColumnNumber (e.g. "A1"). RowLabel is generated by turning an integer (the lock index) into letters (0->A, 1->B, ..., 25->Z, 26->AA, 27->AB, etc.). ColumnNumber is the index of the board in the list sorted by board.address
        - boardId: The address of the board on the bus 
        - lockId: The index of the lock on the board (0 to capacity-1)
        - lockStatus: The status of the lock (True if open, False if closed)
        - openDirection: Default value "right"
        - size: Default value "M"

### Data Structures
- class LockerLayout:
    - columns: list[Column]

- class Column:
    - rows: list[Row]

- class Row:
    - compartments: list[Compartment]

- class Compartment:
    - label: str
    - boardId: str
    - lockId: str 
    - lockStatus: bool
    - openDirection: str
    - size: str



## 1.4. Mapping Store
- The mapping store is responsible for storing the boards found with the Bus Scanner and the layout built by the Layout Builder. It is the "memory" of the system. - For this, it stores data locally in .json files. 
- This component uses and writes to one User Data register of the boards on the bus. For each board, it reads this User Data register, and if its 0, it considers it a new board. After a successful map update, it writes a specific value to the User Data register of the new boards.
- On construction, it loads the data from the .json files (if they exist) to internal variables (these variables are considered the old data when updating the mapping with new data).
- Methods to load/save the list of boards and layout from/to .json files.
- Method to compare mapping, receiving a new list of boards and layout:
    - For each board in the new boards list:
        - It checks the board address was already occupied in the last stored scan. If not, it marks it as a new board.
        - If the new board address was already occupied, it verifies the User Data register 0 to check for a specific value: 0xABCD. If it does not find this value in the register, it marks it as a substitution.
        - To understand if its a substitution, it checks if the new board address was present in the old boards list:
            - If it was, it is a substitution. 
            - If it was not, it is a new board. 
    - After the previous analysis, it compares the old boards list with the new one to find any boards that disappeared. 
        - To understand if a board disappeared, it checks if any board address from the old boards list is not present in the new boards list. If it finds any board that disappear, it adds it to disappeared_boards list.
    - Based on the boards on the new_boards and disappeared_boards lists, it creates a log with the new compartments resulting from the new boards and the disappeared compartments resulting from the disappeared boards or replacements. 
- Method to update the mapping, receiving a new list of boards and layout:
    - It runs the compare mapping method to get the new_boards and disappeared_boards lists.
    - It updates the two .json files with the new received boards list and layout. It also updates the two variables: boards and layout.
    - (Not Implemented in this component) - At the end of the update, the User Data register 0 is to be written with the value 0xABCD for all the new boards and substitutions. However, this is done in the main app directly, on the endpoint /update.
    
### Data Structures
layout: LockerLayout
boards: List[BoardInfo]


## 1.5. Door Service
- Acts as the application's logic for commanding physical doors. 
- Receives human-readable string labels (like "A1", "Z3", "AA1") and abstracts away the underlying hardware complexity.
- Queries the Mapping Store to resolve the label into a specific `boardId` (Modbus Address) and `lockId` (Index on the board).
- Dispatches the hardware actuation command via the Modbus Client (FC05 - Write Single Coil).
- Critically, it implements a synchronous polling loop after actuating the lock to verify the physical door state (via FC03) before responding to the caller, ensuring that a "Success" response means the door actually popped open, not just that a signal was sent.

### Known Issues
- Implemented a close method as well, it effectively closes the lock (verified in serv /ui/bus endpoint) but my endpoint returns a timeout, I believe to be due to the board not updating its lock status register.

## 1.6. Main Apps
- There are 3 apps available to run. Contains 2 primary interfaces
    1. **Headless API (`src/main.py`)**: A FastAPI application that acts as a REST interface. It maintains a centralized, stateful singleton (`State`) holding instances of all the core services (Modbus Client, Bus Scanner, Layout Builder, Mapping Store, Door Service), as well as the boards and layout (last_boards, last_layout) retrieved from the last scan. 
    - Manages two different memory spaces: the in-memory state (boards and layout) and the persistent state (boards and layout in .json files). Exposes endpoints:
        - `POST /scan`: Scans the bus and updates state memory boards.
        - `GET /compare`: Compares state memory boards with .json file stored state to identify new boards, substitutions and disappeared boards.
        - `POST /update`: Updates .json file stored layout/boards from state.
        - `POST /reset_custom_user_data`: Resets the user data register of a specific board to 0x0000.
        - `GET /boards`: Returns the currently scanned in-memory boards.
        - `GET /layout`: Returns the currently built in-memory layout.
        - `GET /stored_boards`: Returns the currently stored boards.
        - `GET /stored_layout`: Returns the currently stored layout.
        - `POST /open`: Opens a compartment by its label (e.g., "A1").
        - `POST /close`: Closes a compartment logically if supported.
        - `POST /dummy`: Adds dummy boards to in-memory state for testing.
        
        
    2. **Interactive CLI (`src/api_repl.py`)**: 
        - Interactive Read-Eval-Print (REPL) Loop used as a frontend mock for the previous FastAPI application, for diagnosing and testing the API endpoints.
        - To use properly, requires `src/main.py` to be running.
        - Press `h` or `help` to see the available commands.
        
    3. **Interactive CLI (`src/main_repl.py`)**: 
        - An independent Interactive REPL Loop used for diagnosing and testing the components locally. The components are used directly in the application.
        - Can be run independently of `src/main.py`. Runs solo.
        - Press `h` or `help` to see the available commands.

# 2. What is the data contract between them?
- **Scanner ↔ Modbus**: Scanner invokes low-level byte frame generation (`read_registers`) through ModbusClient, returning raw bytes.
- **Scanner ↔ Core Memory**: Scanner parses raw bytes into `BoardInfo` dataclasses (representing ID, hardware limits, config, and 1D boolean array for locks).
- **Core Memory ↔ Layout Builder**: Layout builder ingests `List[BoardInfo]` and applies heuristics to group them into a 3D structural tree (`LockerLayout` -> `Column` -> `Row` -> `Compartment`).
- **Core Memory ↔ Mapping Store**: Mapping Store ingests both `BoardInfo` lists and the generated `LockerLayout` to serialize into persistent `.json` files.
- **Mapping Store ↔ Door Service**: DoorService queries the MappingStore's flattened O(1) dictionary dictionary to fetch `Compartment` metadata (routing info) by string label. 

# 3. How does `open("A1")` flow through the system?
1. External user issues `POST /open` with payload `{"label": "A1"}`.
2. FastAPI controller catches the request and passes it to `DoorService.open("A1")`.
3. `DoorService` requests routing data from `MappingStore`.
4. `MappingStore` successfully resolves "A1" to `Compartment(boardId="1", lockId="0")`.
5. `DoorService` calls `ModbusClient.write_single_coil(address=1, lock_id=0, state=True)`.
6. `ModbusClient` calculates the CRC, packs the bytes, and flushes the command down the RS-485 serial wire.
7. `DoorService` enters a polling loop (FC03), repeatedly asking Board 1 for its lock status array.
8. Once Lock 0's bit flips to `False` (Open), polling stops.
9. `DoorService` returns `OpenResult.OK`.
10. FastAPI responds to the user with `200 OK`.

# 4. What happens if a board that was previously seen disappears from the bus?
When a user manually triggers a bus scan (`POST /scan`), the `BoardScanner` attempts to ping all addresses 1-16. If an address that existed in the cached memory times out, the board is effectively dropped from the volatile `active_boards` list.
When the user subsequently runs a comparison (`GET /compare`) or triggers a persistence update (`POST /update`), the `MappingStore` diffs the new `active_boards` against its previously loaded JSON state. It detects that an address acts missing, logs a `Board vanished` warning, and appends it to a `disappeared_boards` list. If the layout is explicitly updated, that column's physical mapping is unlinked and completely destroyed from the next system layout.

# 5. What happens if a new board appears that was not in the stored mapping?
During a scan and subsequent persistence logic (`MappingStore.update_from_scan`), the system leverages the Modbus configurable `user_data[0]` register to intelligently handle new boards:
1. When a new board is picked up, it has an empty `user_data[0]` register of `0x0000`.
2. The logic compares the board's physical RS-485 address against the known addresses in the old mapping data.
3. **If the address is completely new**: It classifies it as a brand new hardware expansion.
4. **If the address matches a missing previously known board**: It classifies it as a **hardware substitution** (e.g. a broken board was physically swapped for a healthy one at the same DIP switch address).
5. During the `POST /update` commit, the API layer proactively fires a Modbus write to securely etch the signature `0xABCD` onto that board's `user_data[0]` register. 
6. This "brands" it as claimed by the software, finalizing the layout expansion and ensuring it won't be treated as new on the next reboot.