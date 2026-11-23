from app.core.tool import BaseTool
from app.core.result import ToolResult


class GotoTool(BaseTool):

    name = "goto"

    description = "打开一个网页"

    parameters = {
        "url": "string"
    }

    async def execute(self, context, **kwargs):

        url = kwargs.get("url")

        if not url:

            return ToolResult(
                success=False,
                error="url is required"
            )

        try:

            await context.page.goto(url)

            context.current_url = url

            return ToolResult(
                success=True,
                data={"url": url},
                message="page loaded"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )