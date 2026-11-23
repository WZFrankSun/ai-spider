from app.core.tool import BaseTool
from app.core.result import ToolResult


class ScrollTool(BaseTool):

    name = "scroll"

    description = "滚动页面"

    parameters = {
        "y": "int"
    }

    async def execute(self, context, **kwargs):

        y = kwargs.get("y", 1000)

        try:

            await context.page.evaluate(f"""
                window.scrollBy(0, {y})
            """)

            return ToolResult(
                success=True,
                data={"y": y},
                message="scrolled"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )