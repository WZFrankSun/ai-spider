from app.core.tool import BaseTool
from app.core.result import ToolResult


class GoBackTool(BaseTool):

    name = "go_back"

    description = "浏览器后退到上一页"

    parameters = {
        "wait_ms": "number",
    }

    async def execute(self, context, **kwargs):

        wait_ms = int(kwargs.get("wait_ms") or 500)

        try:
            await context.page.go_back()
            await context.page.wait_for_load_state("domcontentloaded")
            await context.page.wait_for_timeout(wait_ms)

            context.current_url = context.page.url

            return ToolResult(
                success=True,
                data={"url": context.current_url},
                message="went back",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
