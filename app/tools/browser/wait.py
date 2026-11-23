from app.core.tool import BaseTool
from app.core.result import ToolResult


class WaitTool(BaseTool):

    name = "wait"

    description = "等待页面加载或元素出现"

    parameters = {
        "state": "string",
        "selector": "string",
        "timeout": "number",
        "ms": "number",
    }

    async def execute(self, context, **kwargs):

        selector = kwargs.get("selector")
        state = kwargs.get("state", "networkidle")
        timeout = kwargs.get("timeout", 30000)
        ms = kwargs.get("ms")

        try:

            if ms:
                await context.page.wait_for_timeout(ms)
            elif selector:
                await context.page.wait_for_selector(selector, timeout=timeout)
            else:
                await context.page.wait_for_load_state(state, timeout=timeout)

            return ToolResult(
                success=True,
                data={
                    "state": state,
                    "selector": selector,
                    "timeout": timeout,
                    "ms": ms,
                },
                message="wait success"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )
