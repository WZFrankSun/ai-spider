from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.agents.selector_resolver import SelectorResolver
from app.agents.json_utils import parse_json_response
from app.tools.extract.dom_extract import collect_visible_dom


class AIClickTool(BaseTool):

    name = "ai_click"

    description = "AI自动找到按钮并点击"

    parameters = {
        "task": "string"
    }

    async def _click(self, page, selector: str) -> str:
        locator = page.locator(selector)
        await locator.scroll_into_view_if_needed()

        if await locator.is_visible():
            await locator.click(timeout=5000)
            return "click"

        await locator.click(force=True, timeout=5000)
        return "force_click"

    async def execute(self, context, **kwargs):

        task = kwargs.get("task")

        try:

            dom = await collect_visible_dom(context.page)

            resolver = SelectorResolver()
            result = await resolver.resolve(task, dom, platform=getattr(context, "platform", None))

            if not result:
                return ToolResult(
                    success=False,
                    error="AI selector resolution failed",
                    message="ai click failed"
                )

            data = parse_json_response(result)
            selector = data["selector"]

            click_mode = await self._click(context.page, selector)

            return ToolResult(
                success=True,
                data={
                    "selector": selector,
                    "task": task,
                    "click_mode": click_mode,
                    "reason": data.get("reason"),
                },
                message="ai click success"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                message="ai click failed"
            )
