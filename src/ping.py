import logging
import time
from core.modbus import ModbusClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    client = ModbusClient(port="/tmp/serial_bridge", baudrate=19200)
    logger.info("Connecting to Modbus emulator on /tmp/serial_bridge...")
    
    try:
        client.connect()
        logger.info("Connected successfully.")

        registers_to_scan = [0x00F7, 0x0000]
        
        # Ping address 1, register 0x000F to read Board ID
        # for dip in range(16):
        #     address = dip + 1
            

        #     time.sleep(1)
        address = 1

        # while True:
        logger.info(f"Pinging board address {address}...")
        response = client.read_registers(address=address, register_start=0x000F, register_count=3)
        
        if response:
            logger.info(f"Response received. Type: {type(response)} {type(response[0])}. {hex((response[0] << 8) | response[1])}. {(response[1] >> 4) & 1} Len: {len(response)}. Obj 0: {hex(response[0])}. Obj 1: {response[1]:02X}")
            logger.info(f"Received valid response. Response: {response.hex().upper()}")
        else:
            logger.warning("No valid response received.")

        time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error communicating with Modbus: {e}")
    finally:
        client.disconnect()
        logger.info("Disconnected.")

if __name__ == "__main__":
    main()
