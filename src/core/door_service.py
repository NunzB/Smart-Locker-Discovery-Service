import time
import logging
from core.models import OpenResult
from core.modbus import ModbusClient
from core.mapping_store import MappingStore
from core.scanner import BoardScanner

logger = logging.getLogger(__name__)

class DoorService:
    def __init__(self, modbus_client: ModbusClient, scanner: BoardScanner, mapping_store: MappingStore):
        self.client = modbus_client
        self.scanner = scanner
        self.store = mapping_store

    def open(self, label: str) -> OpenResult:
        """
        Attempts to open a compartment by its string label (e.g., 'A1').
        """
        # Resolve mapping first
        comp = self.store.get_compartment_by_label(label)
        if not comp:
            logger.warning(f"Label '{label}' not found in mapping store.")
            return OpenResult.NOT_FOUND

        address = int(comp.boardId)
        lock_idx = int(comp.lockId)

        logger.info(f"Opening compartment {label} -> Board {address}, Lock Index {lock_idx}")

        # Send unlock frame (FC 0x05)
        success = self.client.write_single_coil(address, lock_idx, True) # True maps to FF 00
        if not success:
            logger.error(f"Failed to send unlock command to board {address}. Board might be offline.")
            return OpenResult.OFFLINE 

        # Poll status
        logger.info("Polling for unlock status...")
        start_time = time.time()
        timeout = 2.0  # 2 seconds max
        
        while time.time() - start_time < timeout:
            is_closed = self.scanner.read_specific_lock_status(address, lock_idx)

            if is_closed is None:
                logger.error(f"Failed to read lock status for compartment {label}. Board might be offline.")
                return OpenResult.OFFLINE
            
            if is_closed == 0:
                logger.info(f"Confirmed compartment {label} is OPEN.")
                return OpenResult.OK
            time.sleep(0.2)
            
        logger.warning(f"Timeout while waiting for compartment {label} to report as OPEN.")
        return OpenResult.TIMEOUT

    def close(self, label: str) -> OpenResult:
        """
        Attempts to close a compartment by its string label (e.g., 'A1').
        """
        # Resolve mapping
        comp = self.store.get_compartment_by_label(label)
        if not comp:
            logger.warning(f"Label '{label}' not found in mapping store.")
            return OpenResult.NOT_FOUND

        address = int(comp.boardId)
        lock_idx = int(comp.lockId)

        logger.info(f"Closing compartment {label} -> Board {address}, Lock Index {lock_idx}")

        # Send unlock frame (FC 0x05)
        success = self.client.write_single_coil(address, lock_idx, False) # False maps to 00 00
        if not success:
            logger.error(f"Failed to send unlock command to board {address}. Board might be offline.")
            return OpenResult.OFFLINE 

        # Poll status
        logger.info("Polling for unlock status...")
        start_time = time.time()
        timeout = 2.0  # 2 seconds max
        
        while time.time() - start_time < timeout:
            is_closed = self.scanner.read_specific_lock_status(address, lock_idx)

            if is_closed is None:
                logger.error(f"Failed to read lock status for compartment {label}. Board might be offline.")
                return OpenResult.OFFLINE
            
            if is_closed == 1:
                logger.info(f"Confirmed compartment {label} is CLOSED.")
                return OpenResult.OK
            time.sleep(0.2)
            
        logger.warning(f"Timeout while waiting for compartment {label} to report as CLOSED.")
        return OpenResult.TIMEOUT
