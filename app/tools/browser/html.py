from app.core.tool import BaseTool
from app.core.result import ToolResult


class HtmlTool(BaseTool):

    name = "html"

    description = "获取当前页面HTML"

    parameters = {}

    async def execute(self, context, **kwargs):

        try:

            html = await context.page.content()

            return ToolResult(
                success=True,
                data={"html": html},
                message="html extracted"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )