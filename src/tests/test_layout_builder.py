import pytest
from core.models import BoardInfo

from core.layout_builder import LayoutBuilder, get_row_label

def test_row_naming():
    """Test Case 2: A..Z naming up to AV"""
    assert get_row_label(0) == "A"
    assert get_row_label(1) == "B"
    assert get_row_label(25) == "Z"
    assert get_row_label(26) == "AA"
    assert get_row_label(47) == "AV"

def test_mixed_boards_layout():
    """Test Case 1: Mixed Boards (48 + 24)"""
    b1 = BoardInfo(address=1, model={224: "NCU48L"}, capacity=48)
    b2 = BoardInfo(address=2, model={224: "NCU24L"}, capacity=24)
    
    builder = LayoutBuilder()
    layout = builder.build([b1, b2])
    
    assert len(layout.columns) == 2
    
    # Check column 1 (address 1, 48 locks)
    col1 = layout.columns[0]
    assert len(col1.rows) == 48
    assert col1.rows[0].compartments[0].label == "A1"
    assert col1.rows[0].compartments[0].boardId == "1"
    assert col1.rows[26].compartments[0].label == "AA1"
    assert col1.rows[-1].compartments[0].label == "AV1"
    
    # Check column 2 (address 2, 24 locks)
    col2 = layout.columns[1]
    assert len(col2.rows) == 24
    assert col2.rows[0].compartments[0].label == "A2"
    assert col2.rows[0].compartments[0].boardId == "2"
    assert col2.rows[23].compartments[0].label == "X2"
