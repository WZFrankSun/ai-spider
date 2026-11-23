from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolResult:
    success: bool

    data: Any = None # 工具执行结果

    message: str = "" # 工具执行消息

    error: Optional[str] = None # 工具执行错误