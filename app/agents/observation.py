from dataclasses import dataclass
from typing import Any


@dataclass
class Observation:

    tool: str

    success: bool

    data: Any

    error: str = ""