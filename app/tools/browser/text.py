from app.core.tool import BaseTool
from app.core.result import ToolResult


class TextTool(BaseTool):

    name = "text"

    description = "获取页面文本"

    parameters = {
        "selector": "string"
    }

    async def execute(self, context, **kwargs):

        selector = kwargs.get("selector")

        try:

            if selector:

                text = await context.page.locator(selector).inner_text()

            else:

                text = await context.page.inner_text("body")

            return ToolResult(
                success=True,
                data={"text": text},
                message="text extracted"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )