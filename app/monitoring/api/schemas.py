from typing import Literal

from pydantic import BaseModel


class DemoResultRequest(BaseModel):
    result: Literal["healthy", "inventory_risk", "technical_failure"]
