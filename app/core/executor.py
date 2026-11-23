from .result import ToolResult
from .registry import ToolRegistry


class ToolExecutor:

    '''
        工具执行器
    '''

    def __init__(self, registry: ToolRegistry):
        '''
            初始化工具执行器
        '''

        self.registry = registry

    async def execute(self, tool_name: str, context, **kwargs) -> ToolResult:

        '''
            执行一个工具
        '''

        tool_cls = self.registry.get(tool_name)

        if not tool_cls:

            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}"
            )

        tool = tool_cls()

        try:

            result = await tool.execute(context, **kwargs)

            return result

        except Exception as e:

            '''
                工具执行异常
            '''

            return ToolResult(
                success=False,
                error=str(e)
            )