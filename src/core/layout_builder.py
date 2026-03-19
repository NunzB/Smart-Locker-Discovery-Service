from typing import List
from core.models import BoardInfo, LockerLayout, Column, Row, Compartment

def get_row_label(index: int) -> str:
    """Converts an integer index to an alphabetical row label (0->A, 25->Z, 26->AA)."""
    result = ""
    index += 1
    while index > 0:
        index -= 1
        result = chr((index % 26) + ord('A')) + result
        index //= 26
    return result

def get_row_from_label(label: str) -> int:
    """Converts an alphabetical row label to an integer index (A->0, Z->25, AA->26)."""
    index = 0
    for char in label:
        index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1

class LayoutBuilder:
    def build(self, active_boards: List[BoardInfo]) -> LockerLayout:
        """
        Reconstructs the LockerLayout heuristically from a list of active boards.
        Assume 1 Board = 1 Column.
        Each lock is a new row in that column.
        """
        layout_columns = []
        
        # Sort boards by address to assign columns consistently
        for col_idx, board in enumerate(sorted(active_boards, key=lambda b: b.address)):
            # Column number is the index of the board in the sorted list + 1 (no column 0)
            col_number = str(col_idx + 1)
            
            rows = []
            # Creating a row for each lock in the board, this assumes a single compartment per row
            for lock_idx in range(board.capacity):
                row_label = get_row_label(lock_idx)
                compartment_label = f"{row_label}{col_number}"
                
                # Defaulting openDirection / size ( to M, right)
                size = "M"
                open_dir = "right"
                
                lock_status = False
                if board.lock_status is not None and lock_idx < len(board.lock_status):
                    lock_status = board.lock_status[lock_idx]
                
                # Bundle all hardware specifics (board ID, lock index) inside the compartment
                # model. This abstraction is key: later services (like door_service) only need 
                # to know a compartment's label to act on it, isolating them from hardware topologies.
                compartment = Compartment(
                    label=compartment_label,
                    boardId=str(board.address),
                    lockId=str(lock_idx),
                    lockStatus=lock_status,
                    openDirection=open_dir,
                    size=size
                )
                
                # Encapsulate the compartment in a Row structural container
                rows.append(Row(compartments=[compartment]))
                
            # Finish building the column representing the entire physical board
            layout_columns.append(Column(rows=rows))
            
        return LockerLayout(columns=layout_columns)
