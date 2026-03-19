import enum
from dataclasses import dataclass, field
from typing import Dict, List


class OpenResult(enum.Enum):
    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"

@dataclass
class BoardConfig:
    sw_version: int = 0
    hw_version: int = 0
    mV: int = 0
    baudrate: int = 0
    opening_time: int = 0
    led_time: int = 0
    user_data: List[int] = field(default_factory=lambda: [0] * 10)

@dataclass
class BoardCounters:
    IRports: List[int] = field(default_factory=lambda: [0] * 4)

@dataclass
class BoardInfo:
    address: int
    model: Dict[int, str] = field(default_factory=dict)
    capacity: int = 48
    config: BoardConfig = None
    counters: BoardCounters = None
    lock_status: List[bool] = field(default_factory=list)
    
 
@dataclass
class Compartment:
    label: str
    boardId: str
    lockId: str 
    lockStatus: bool
    openDirection: str
    size: str


@dataclass
class Row:
    compartments: list[Compartment] = field(default_factory=list)


@dataclass
class Column:
    rows: list[Row] = field(default_factory=list)


@dataclass
class LockerLayout:
    columns: list[Column] = field(default_factory=list)
