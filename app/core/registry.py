from typing import Dict, Type

from .tool import BaseTool


class ToolRegistry:

    '''
        工具注册表
    '''

    def __init__(self):

        self._tools: Dict[str, Type[BaseTool]] = {}

    def register(self, tool_cls: Type[BaseTool]):
        '''
            注册一个工具
        '''

        instance = tool_cls()

        self._tools[instance.name] = tool_cls

    def get(self, name: str):
        '''
            获取一个工具
        '''
        return self._tools.get(name)

    def list_tools(self):
        '''
            获取所有工具
        '''
        return list(self._tools.keys())

    def describe_tools(self) -> str:
        '''
            生成供 LLM 使用的工具描述
        '''
        if not self._tools:
            return "(no tools registered)"

        lines = []
        for name in sorted(self._tools):
            tool = self._tools[name]()
            params = ", ".join(
                f"{key}: {value}" for key, value in tool.parameters.items()
            )
            signature = f"({params})" if params else "()"
            lines.append(f"- {name}{signature}: {tool.description}")

        return "\n".join(lines)