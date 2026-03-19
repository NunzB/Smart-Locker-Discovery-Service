import platform
import serial
import time
import logging
from typing import Union, List

logger = logging.getLogger(__name__)

# CRC helpers from Appendix 4
def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(frame: bytes) -> bytes:
    c = crc16_modbus(frame)
    return frame + bytes([c & 0xFF, (c >> 8) & 0xFF])


def check_crc(frame: bytes) -> bool:
    if len(frame) < 3:
        return False
    data, crc = frame[:-2], frame[-2:]
    c = crc16_modbus(data)
    return (crc[0] == (c & 0xFF)) and (crc[1] == ((c >> 8) & 0xFF))


class ModbusClient:
    """
    Low-level serial wrapper implementing a subset of the Modbus RTU protocol.
    Allows tight control of the frame composition 
    """
    def __init__(self, port: str = "/dev/ttyV0", baudrate: int = 19200, timeout: float = 0.5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None

    def connect(self):
        logger.info(f"Connecting to serial bridge client on port {self.port}...")
        if not self.serial_conn or not self.serial_conn.is_open:
            try:
                self.serial_conn = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=self.timeout
                )
            except Exception as e:
                logger.error(f"Failed to connect to {self.port}: {e}")
                raise

    def disconnect(self):
        logger.info("Disconnecting from Serial Bridge Client...")
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

    def send_and_receive(self, frame: bytes, expected_length: int = 256) -> bytes:
        """
        The core communication loop. Handles the CRC appending, flushing stale buffers, 
        and blocking until the expected bytes arrive or the timeout is hit. Verifies CRC of response.
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            self.connect()

        self.serial_conn.reset_input_buffer()
        self.serial_conn.reset_output_buffer()

        frame_with_crc = append_crc(frame)

        logger.info(f"Sending frame: 0x{frame_with_crc.hex().upper()}")

        self.serial_conn.write(frame_with_crc)
        self.serial_conn.flush()

        response = self.serial_conn.read(expected_length)
        
        if not response:
            logger.warning(f"No response received")
            return b""
            
        if not check_crc(response):
            logger.warning(f"CRC check failed for response: {response.hex()}")
            return b""
            
        logger.info(f"Received valid response: 0x{response.hex().upper()}")
        
        return response

    def read_registers(self, address: int, register_start: int, register_count: int) -> bytes:
        """
        Function Code 03: Read Registers
        Used to fetch configuration, counters, etc. Pass the 
        exact amount of registers to minimize serial-bus transmission time and receive response in bulk.
        """

        logger.info(f"Reading registers for address {address}. Register start: 0x{register_start:04X}, Register count: {register_count}")
        # [Address, 0x03, Start_Hi, Start_Lo, Count_Hi, Count_Lo]
        frame = bytes([
            address,
            0x03,
            (register_start >> 8) & 0xFF,
            register_start & 0xFF,
            (register_count >> 8) & 0xFF,
            register_count & 0xFF
        ])
        
        # Expected length = 1 (addr) + 1 (FC) + 1 (byte count) + 2 * register_count + 2 (CRC)
        expected_len = 5 + 2 * register_count
        response = self.send_and_receive(frame, expected_len)
        
        if len(response) == expected_len and response[1] == 0x03:
            return response[3:-2] # Return just the data bytes
        return b""
 
    def write_single_coil(self, address: int, coil_address: int, state: bool) -> bool:
        """Function Code 05: Write Single Coil"""
        # [Address, 0x05, Coil_Hi, Coil_Lo, Data_Hi, Data_Lo]
        # For FC 05: Open is FF 00 (according to appendix)
        data_hi = 0xFF if state else 0x00
        data_lo = 0x00
        
        frame = bytes([
            address,
            0x05,
            (coil_address >> 8) & 0xFF,
            coil_address & 0xFF,
            data_hi,
            data_lo
        ])
        
        expected_len = 8 # 1+1+2+2+2
        response = self.send_and_receive(frame, expected_len)
        
        if len(response) == expected_len and response[1] == 0x05:
            return True
        return False

    def write_single_register(self, address: int, register_address: int, value: int) -> bool:
        """Function Code 06: Write Single Register"""
        frame = bytes([
            address,
            0x06,
            (register_address >> 8) & 0xFF,
            register_address & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF
        ])
        
        expected_len = 8
        response = self.send_and_receive(frame, expected_len)
        
        if len(response) == expected_len and response[1] == 0x06:
            return True
        return False
