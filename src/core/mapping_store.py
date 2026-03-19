import os
import json
import logging
from dataclasses import asdict
from typing import List, Dict

from core.models import LockerLayout, Column, Row, Compartment, BoardInfo
from core.layout_builder import LayoutBuilder

logger = logging.getLogger(__name__)

CONST_USER_DATA_REG_ADDRESS = 0x0000
CONST_USER_DATA_REG_VALUE = 0xABCD

class MappingStore:
    """
    Acts as the persistant source of truth for the locker system's configuration.
    It bridges the gap between the volatile hardware state (what the boards report right now)
    and the persistent state (what we expect the configuration to be based on past scans).
    By maintaining an O(1) lookup dictionary for compartments, it ensures that high-frequency
    operations (like opening a door) don't need to traverse the entire layout tree.
    """
    def __init__(self, layout_filepath: str = "data/locker_layout.json", boards_filepath: str = "data/locker_boards.json"):
        self.boards_filepath = boards_filepath
        self.layout_filepath = layout_filepath
        
        self.boards: List[BoardInfo] = []
        self.layout: LockerLayout | None = None
        self.compartments_by_label: Dict[str, Compartment] = {}
        
        self.load_layout()
        self.load_boards()
 
    def load_layout(self):
        if not os.path.exists(self.layout_filepath):
            self.layout = None
            self._rebuild_compartments()
            return
            
        try:
            with open(self.layout_filepath, 'r') as f:
                data = json.load(f)
                self.layout = self._dict_to_layout(data)
                logger.info(f"Loaded existing layout from {self.layout_filepath}")
        except Exception as e:
            logger.error(f"Failed to load layout from {self.layout_filepath}: {e}")
            self.layout = None

        # Having secondary indexing (compartments_by_label) is vital for performance.
        self._rebuild_compartments()

    def _dict_to_layout(self, data: dict) -> LockerLayout:
        cols = []
        for col_data in data.get("columns", []):
            rows = []
            for row_data in col_data.get("rows", []):
                comps = []
                for comp_data in row_data.get("compartments", []):
                    comps.append(Compartment(**comp_data))
                rows.append(Row(compartments=comps))
            cols.append(Column(rows=rows))
        return LockerLayout(columns=cols)

    def save_layout(self):
        if self.layout:
            try:
                os.makedirs(os.path.dirname(self.layout_filepath), exist_ok=True)
                with open(self.layout_filepath, 'w') as f:
                    json.dump(asdict(self.layout), f, indent=2)
                logger.info(f"Saved layout to {self.layout_filepath}")
            except Exception as e:
                logger.error(f"Failed to save layout: {e}")

    def load_boards(self):
        if not os.path.exists(self.boards_filepath):
            self.boards = []
            return
            
        try:
            with open(self.boards_filepath, 'r') as f:
                data = json.load(f)
                self.boards = [BoardInfo(**b) for b in data]
                logger.info(f"Loaded existing boards from {self.boards_filepath}")
        except Exception as e:
            logger.error(f"Failed to load boards from {self.boards_filepath}: {e}")
            self.boards = []

    def save_boards(self):
        if self.boards:
            try:
                os.makedirs(os.path.dirname(self.boards_filepath), exist_ok=True)
                with open(self.boards_filepath, 'w') as f:
                    json.dump([asdict(b) for b in self.boards], f, indent=2)
                logger.info(f"Saved boards to {self.boards_filepath}")
            except Exception as e:
                logger.error(f"Failed to save boards: {e}")

    def compare_with_stored_data(self, active_boards: List[BoardInfo], new_layout: LockerLayout):
        """
        Compares the given active_boards and new_layout with the currently stored boards and layout,
        identifying new boards, substitutions, and disappeared boards, and logging the differences.
        """
        new_boards_list = []
        disappeared_boards_list = []

        logger.info(f"Comparing boards with stored data: {len}")
        
        old_addresses = {b.address for b in self.boards}
        new_addresses = {b.address for b in active_boards}
        
        # 1. Determine New Boards / Substitutions based on user data register
        for board in active_boards:
            if board.address not in old_addresses:
                new_boards_list.append({"board": board, "substitution": False})
                logger.info(f"New board found at address {board.address}")
            # If the user data reg is not 0xABCD, it's a new board
            elif board.config.user_data[0] != 0xABCD:
                new_boards_list.append({"board": board, "substitution": True})
                logger.info(f"Substitution Board found at address {board.address}")
                
        # for board in active_boards:
        #     # simplify to Address matching as the primary substitution metric for this example
        #     if board.address not in old_addresses:
        #         new_boards_list.append({"board": board, "substitution": False})
        #         logger.info(f"New board found at address {board.address}")
        #     else:
        #         pass

        # 2. Determine Disappeared Boards
        for old_board in self.boards:
            if old_board.address not in new_addresses:
                disappeared_boards_list.append(old_board)
                logger.warning(f"Board vanished at address {old_board.address}")
        
        return new_boards_list, disappeared_boards_list

    def update_from_scan(self, active_boards: List[BoardInfo], new_layout: LockerLayout):
        """
        Updates the mapping store using the newly scanned active_boards and newly built LockerLayout.
        """
        new_boards_list, disappeared_boards_list = self.compare_with_stored_data(active_boards, new_layout)
            
        #  Set internal state 
        self.boards = active_boards
        self.layout = new_layout
        self._rebuild_compartments()
        
        # Save state to .json files
        self.save_boards()
        self.save_layout()
        
        return new_boards_list, disappeared_boards_list

    def get_compartment_by_label(self, label: str) -> Compartment | None:
        """
        Get a Compartment object by its label string in O(1) time.
        """
        return self.compartments_by_label.get(label.upper())

    def _rebuild_compartments(self):
        """
        Rebuilds the flattened dictionary for searches by compartment label.
        This flattening transforms an O(N) search into an O(1) 
        """
        self.compartments_by_label = {}
        if not self.layout:
            return
        
        for col in self.layout.columns:
            for row in col.rows:
                for comp in row.compartments:
                    self.compartments_by_label[comp.label.upper()] = comp