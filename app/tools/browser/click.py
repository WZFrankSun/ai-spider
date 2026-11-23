from app.core.tool import BaseTool
from app.core.result import ToolResult


class ClickTool(BaseTool):

    name = "click"

    description = "点击页面元素"

    parameters = {
        "selector": "string"
    }

    async def execute(self, context, **kwargs):

        selector = kwargs.get("selector")

        if not selector:

            return ToolResult(
                success=False,
                error="selector is required"
            )

        try:

            await context.page.click(selector)

            return ToolResult(
                success=True,
                data={"selector": selector},
                message="clicked"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )