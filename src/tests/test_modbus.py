import pytest
from core.modbus import crc16_modbus, append_crc, check_crc

def test_crc16_logic():
    """Test Appendix 4 CRC check logic"""
    # 0x000F Example from the appendix: 01 03 00 0F 00 01 B4 09
    frame = bytes.fromhex("01 03 00 0F 00 01")
    crc = crc16_modbus(frame)
    # The CRC bytes appended are [Low, High]
    # B4 09 means Low=0xB4, High=0x09 -> integer is 0x09B4
    assert crc == 0x09B4
    
    appended = append_crc(frame)
    assert appended == bytes.fromhex("01 03 00 0F 00 01 B4 09")
    
    assert check_crc(appended) is True
    
    # Ensure invalid CRC fails
    invalid_frame = bytes.fromhex("01 03 00 0F 00 01 B4 0A")
    assert check_crc(invalid_frame) is False
