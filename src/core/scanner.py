import logging
from typing import List, Dict, Optional
from core.models import BoardInfo, BoardConfig, BoardCounters
from core.modbus import ModbusClient
from math import ceil

logger = logging.getLogger(__name__)

# Model mapping (High Byte -> Model Name)
MODEL_MAP = {
    0xE0: "NCU48L",
    0xE1: "NCU48L_Infrared",
    0xE2: "NCU48L_LowPower_Std",
    0xE4: "NCU48L_LowPower",
    0xA0: "NCU24L",
    0x80: "NCU16L",
    0x40: "NCU12L_8L",
}

class BoardScanner:
    """
    Responsible for interrogating the physical Modbus network to discover active locking boards.
    It builds a rich model (BoardInfo) out of low-level hexadecimal Modbus responses.
    """
    def __init__(self, modbus_client: ModbusClient):
        self.client = modbus_client

        # Address blacklist - Add addresses not to scan
        self.blacklist: List[int] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        # self.blacklist: List[int] = []

    def scan_bus(self) -> List[BoardInfo]:
        """Scans addresses 1 to 16 (DIP 0-15 + 1) to find active boards on the bus."""
        active_boards = []
        for dip in range(16):
            address = dip + 1
            if address in self.blacklist:
                continue
            board = self._scan_board(address)
            if board:
                active_boards.append(board)
        return active_boards

    def read_specific_lock_status(self, address: int, lock_id: int) -> Optional[bool]:
        """
        Queries a specific address for its lock status.
        Returns a boolean.
        0 = open, 1 = closed
        """

        lock_status: List[bool] = []

        # Read lock status - Only read the specific register we need for this lock id
        reg_addr = (lock_id // 16)
        status_res = self.client.read_registers(address, 0x0000 + reg_addr, 1)

        # If the board does not respond or has an unexpected response, return None
        if status_res is None or len(status_res) != 2:
            return None 

        # Get the specific lock id from the register based on the remainder of the division of lock_id per 16
        # This accounts for the skipped registers
        lock_id_bit = lock_id % 16
        lock_id_status = (status_res[0] >> lock_id_bit) & 1

        # Return true if the lock is closed, false if the lock is open
        return lock_id_status == 1


    def _scan_board(self, address: int) -> Optional[BoardInfo]:
        """
        Queries a specific address for its status and type.
        Returns a BoardInfo object if successful, None if it times out/fails to respond on status.
        """

        board = BoardInfo(address=address)
        
        # Default values for capacity and model name
        default_capacity = 48
        default_model_name = "UNKNOWN"
        
        # Read Board ID register (0x000F)
        type_res = self.client.read_registers(address, 0x000F, 1)
        
        if type_res is None or len(type_res) != 2:
            # A board that does not respond or has an unexpected response is considered absent
            return None 
        
        # Get model (High Byte) and max capacity (Low Byte)
        model = type_res[0]
        max_capacity = type_res[1] 
        
        if model in MODEL_MAP:
            # If the model is defined, set model string
            board.model[model] = MODEL_MAP[model]
            board.capacity = max_capacity
        else:
            # If the model is not found (considered as board type read failed), defaults to 48 capacity and log a warning
            logger.warning(f"Unknown board type 0x{model:02X} with capacity {max_capacity} at addr {address}. Defaulting to 48 capacity.")
            board.model[model] = default_model_name
            board.capacity = default_capacity
                

        # Read board configuration
        board.config = self._read_board_config(address)

        # Read board counters
        board.counters = self._read_board_counters(address)

        # Read lock status
        board.lock_status = self._read_lock_status(address, board.capacity)


        return board


    def _read_board_counters(self, address:int) -> BoardCounters:
        """
        Queries a specific address for the Counters registers: 
            - 0x0090 - 0x0093: 
                IR Counter - 4 registers, 16 bits each
        Returns a BoardCounters object if successful, None if it times out/fails to respond on status.
        """
        counters = BoardCounters()

        # Read IR Counter registers (0x0090 - 0x0093) - 4 registers, 16 bits each
        logger.info(f"Reading IR Counter registers...")
        num_ir_counter_regs = 4
        ir_res = self.client.read_registers(address, 0x0090, num_ir_counter_regs)
        if(len(ir_res) == num_ir_counter_regs * 2):
            for i in range(num_ir_counter_regs):
                counters.IRports[i] = ir_res[i*2] << 8 | ir_res[i*2 + 1]
        else:
            logger.warning(f"Failed to read IR counters at addr {address}. Defaulting to 0.")
        
        return counters
        

    def _read_board_config(self, address: int) -> BoardConfig:
        """
        Queries a specific address for the Config registers: 
            - 0x00F5: 
                Firmware Version - High byte = SW version, Low byte = HW version
            - 0x00F7: 
                Voltage - mV units
            - 0x00F2: 
                Baud Rate - 0 = 9600, 1 = 19200
            - 0x00F0: 
                Opening Time - Multiply register value by 10 to get the value in ms.
            - 0x00F8: 
                LED Time - Unit seconds. Default 5s.
            - 0x0070 - 0x0079: 
                User Data - 10 registers, 16 bits each
        Returns a BoardInfo object if successful, None if it times out/fails to respond on status.
        """

        # Board Config obj to return
        config = BoardConfig()
 
        # Read Firmware Version register (0x00F5) - High byte = SW version, Low byte = HW version
        logger.info(f"Reading Firmware Version register...")
        fw_res = self.client.read_registers(address, 0x00F5, 1)
        config.sw_version = (fw_res[0]) if (fw_res and len(fw_res) == 2) else 0
        config.hw_version = (fw_res[1]) if (fw_res and len(fw_res) == 2) else 0

        # Read Voltage register (0x00F7) - mV units. 2 bytes
        logger.info(f"Reading Voltage register...")
        volt_res = self.client.read_registers(address, 0x00F7, 1)
        config.mV = (volt_res[0] << 8) | volt_res[1] if (volt_res and len(volt_res) == 2) else 0

        # Read Baud Rate register (0x00F2) - 0 = 9600, 1 = 19200
        logger.info(f"Reading Baud Rate register...")
        baud_res = self.client.read_registers(address, 0x00F2, 1)
        config.baudrate = 19200 if (baud_res and len(baud_res) > 0 and baud_res[0] == 1) else 9600

        # Read Opening Time register (0x00F0) - Multiply register value by 10 to get the value in ms.
        logger.info(f"Reading Opening Time register...")
        opening_res = self.client.read_registers(address, 0x00F0, 1)
        config.opening_time = ((opening_res[0] << 8) | opening_res[1]) * 10 if (opening_res and len(opening_res) == 2) else 0

        # Read LED Time register (0x00F8) - Unit seconds. Default 5s.
        logger.info(f"Reading LED Time register...")
        led_res = self.client.read_registers(address, 0x00F8, 1)
        config.led_time = (led_res[0] << 8 | led_res[1]) if (led_res and len(led_res) == 2) else 5

        # Read User Data registers (0x0070 - 0x0079) - 10 registers, 16 bits each
        logger.info(f"Reading User Data registers...")
        num_user_data_regs = 10
        user_data_res = self.client.read_registers(address, 0x0070, num_user_data_regs)

        if(len(user_data_res) == num_user_data_regs * 2):
            for i in range(num_user_data_regs):
                config.user_data[i] = user_data_res[i*2] << 8 | user_data_res[i*2 + 1]
        else:
            logger.warning(f"Failed to read user data registers at addr {address}. Defaulting to 0.")
            
        return config


    def _read_lock_status(self, address: int, capacity: int) -> List[bool]:
        """
        Queries a specific address for its lock status.
        Returns a list of booleans where True means the lock is closed.
        0 = open, 1 = closed
        """
        lock_status: List[bool] = []

        # Read lock status - Num registers = round up (capacity / 16) - 1 bit per lock
        logger.info(f"Reading Lock Status registers...")
        num_lock_regs = ceil(capacity / 16)
        status_res = self.client.read_registers(address, 0x0000, num_lock_regs)
        
        # Assuming the bits 0...N grow per register.
        # This means the 1st lock is the LSB of the 1st register, the 16th lock is the MSB of the 1st register.
        # The 17th lock is the LSB of the 2nd register, and so on.
        lock_index = 0
        # Loop over status_res in steps of 2 to get 16bit words
        for i in range(0, num_lock_regs * 2, 2):
            # Build full 16bit word
            high_byte = status_res[i]
            low_byte = status_res[i+1]
            reg_word = (high_byte << 8) | low_byte

            # Loop over bits of the 16bit word
            for bit in range(16):
                if lock_index >= capacity:
                    break
                # Append true if bit is 1 (closed), false if bit is 0 (open)
                lock_status.append((reg_word >> bit) & 1 == 1)
                lock_index += 1
        
        return lock_status

    