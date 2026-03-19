import pytest
import copy
from core.models import BoardInfo, BoardConfig, LockerLayout, Column, Row, Compartment
from core.layout_builder import LayoutBuilder
from core.mapping_store import MappingStore

def test_simple_single_board_detection():
    """Simple single-board detection — 1 board (48 locks) returns correct locks count and mapping → PASS."""
    builder = LayoutBuilder()
    b1 = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48, config=BoardConfig(), lock_status=[False]*48)
    
    layout = builder.build([b1])
    
    assert len(layout.columns) == 1
    assert len(layout.columns[0].rows) == 48
    assert layout.columns[0].rows[0].compartments[0].label == "A1"
    # Row 48 is index 47. 0->A, 25->Z, 26->AA ... 47->AV
    assert layout.columns[0].rows[-1].compartments[0].label == "AV1"

def test_mixed_boards():
    """Mixed boards — bus contains 48+24 boards; layout groups them into columns correctly → PASS."""
    builder = LayoutBuilder()
    b1 = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48, config=BoardConfig(), lock_status=[False]*48)
    b2 = BoardInfo(address=2, model={224: "NCU24L"}, capacity=24, config=BoardConfig(), lock_status=[False]*24)
    
    layout = builder.build([b1, b2])
    
    assert len(layout.columns) == 2
    assert len(layout.columns[0].rows) == 48
    assert len(layout.columns[1].rows) == 24
    assert layout.columns[0].rows[0].compartments[0].label == "A1"
    assert layout.columns[1].rows[0].compartments[0].label == "A2"
    assert layout.columns[1].rows[-1].compartments[0].label == "X2"

def test_board_replacement(tmp_path):
    """Board replacement — replace a board ID with same board type; stored mapping is reapplied → PASS."""
    # Setup temporary persistence
    layout_file = tmp_path / "layout.json"
    boards_file = tmp_path / "boards.json"
    store = MappingStore(layout_filepath=str(layout_file), boards_filepath=str(boards_file))
    builder = LayoutBuilder()
    
    # 1. Original board scan and store update
    # Note: A real mapped board has 0xABCD in its user_data[0] register.
    b1 = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48, config=BoardConfig(user_data=[0xABCD]*10), lock_status=[False]*48)
    layout1 = builder.build([b1])
    store.update_from_scan([b1], layout1)
    
    # Verify initial mapping works
    comp_a1 = store.get_compartment_by_label("A1")
    assert comp_a1.boardId == "1"
    
    # 2. Board Replacement Scenario (Hardware Swap)
    # A new board of the same type is plugged into address 1.
    # Its user_data register will be default (0x0000), not the signature 0xABCD.
    b1_new = copy.deepcopy(b1)
    b1_new.config.user_data = [0x0000]*10
    layout2 = builder.build([b1_new])
    
    # Apply the scan with the swapped board
    new_b2, dis_b2 = store.update_from_scan([b1_new], layout2)
    
    # Assertions: We successfully identified it as a substitution, NOT a completely unseen address.
    assert len(new_b2) == 1
    assert new_b2[0]['substitution'] is True
    assert new_b2[0]['board'].address == 1
    
    # Assertions: Even after replacement, the semantic mapping (A1 maps to Board 1, Lock 0) remains fully intact.
    comp_a1_new = store.get_compartment_by_label("A1")
    assert comp_a1_new is not None
    assert comp_a1_new.boardId == "1"
