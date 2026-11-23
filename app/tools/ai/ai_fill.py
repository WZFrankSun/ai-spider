from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.agents.selector_resolver import SelectorResolver
from app.agents.json_utils import parse_json_response
from app.tools.extract.dom_extract import collect_visible_dom


class AIFillTool(BaseTool):

    name = "ai_fill"

    description = "向输入框填入文本，可通过 selector 或 task 定位输入框"

    parameters = {
        "selector": "string",
        "text": "string",
        "task": "string",
    }

    async def execute(self, context, **kwargs):

        selector = kwargs.get("selector")
        text = kwargs.get("text")
        task = kwargs.get("task")

        if not text:
            return ToolResult(
                success=False,
                error="text is required",
            )

        try:

            if not selector:
                if not task:
                    return ToolResult(
                        success=False,
                        error="selector or task is required",
                    )

                dom = await collect_visible_dom(context.page)
                resolver = SelectorResolver()
                result = await resolver.resolve(
                    f"找到用于以下任务的输入框：{task}",
                    dom,
                    platform=getattr(context, "platform", None),
                )

                if not result:
                    return ToolResult(
                        success=False,
                        error="failed to resolve input selector",
                    )

                data = parse_json_response(result)
                selector = data["selector"]

            locator = context.page.locator(selector)
            await locator.scroll_into_view_if_needed()
            await locator.fill(text)

            return ToolResult(
                success=True,
                data={
                    "selector": selector,
                    "text": text,
                    "task": task,
                },
                message="filled",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
