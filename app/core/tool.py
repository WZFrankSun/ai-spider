from abc import ABC, abstractmethod
from typing import Dict, Any

from .result import ToolResult


class BaseTool(ABC):

    '''
        工具基类
    '''
    name: str = "" # 工具名称

    description: str = "" # 工具描述

    parameters: Dict[str, Any] = {} # 工具参数

    @abstractmethod
    async def execute(self, context, **kwargs) -> ToolResult:
        pass