import pytest
from core.models import BoardInfo, BoardConfig
from core.layout_builder import LayoutBuilder
from core.mapping_store import MappingStore

def test_board_replacement(tmp_path):
    layout_filepath = tmp_path / "locker_layout.json"
    boards_filepath = tmp_path / "locker_boards.json"
    store = MappingStore(layout_filepath=str(layout_filepath), boards_filepath=str(boards_filepath))
    builder = LayoutBuilder()
    
    # Initial scan: address 1 (48), address 2 (24) plugged in. Note the 0xABCD user_data.
    b1 = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48, config=BoardConfig(user_data=[0xABCD]*10))
    b2 = BoardInfo(address=2, model={224: "NCU24L"}, capacity=24, config=BoardConfig(user_data=[0xABCD]*10))
    
    layout1 = builder.build([b1, b2])
    store.update_from_scan([b1, b2], layout1)
    
    assert len(store.layout.columns) == 2
    
    # Simulate swap: Address 1 board dies. A brand new NCU48L is plugged into Address 1.
    # Its user_data register is empty (0x0000)
    b1_new = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48, config=BoardConfig(user_data=[0x0000]*10))
    
    store2 = MappingStore(layout_filepath=str(layout_filepath), boards_filepath=str(boards_filepath))
    layout2 = builder.build([b1_new, b2])
    
    new_boards, disappeared = store2.update_from_scan([b1_new, b2], layout2)
    
    # Verify substitution detected
    assert len(new_boards) == 1
    assert new_boards[0]["board"].address == 1
    assert new_boards[0]["substitution"] is True
    
    # Verify mapping retained perfectly
    c_a1 = store2.get_compartment_by_label("A1")
    assert c_a1 is not None
    assert c_a1.boardId == "1"
    
    c_a2 = store2.get_compartment_by_label("A2")
    assert c_a2 is not None
    assert c_a2.boardId == "2"

def test_new_boards_appended(tmp_path):
    layout_filepath = tmp_path / "locker_layout.json"
    boards_filepath = tmp_path / "locker_boards.json"
    store = MappingStore(layout_filepath=str(layout_filepath), boards_filepath=str(boards_filepath))
    builder = LayoutBuilder()
    
    b1 = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48, config=BoardConfig(user_data=[0xABCD]*10))
    layout1 = builder.build([b1])
    store.update_from_scan([b1], layout1)
    
    b2 = BoardInfo(address=2, model={224: "NCU24L"}, capacity=24, config=BoardConfig(user_data=[0xABCD]*10))
    layout2 = builder.build([b1, b2])
    store.update_from_scan([b1, b2], layout2)
    
    # It should have appended the new board as column 2
    assert len(store.layout.columns) == 2
    c_a2 = store.get_compartment_by_label("A2")
    assert c_a2 is not None
    assert c_a2.boardId == "2"
