from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.agents.selector_resolver import SelectorResolver
from app.agents.json_utils import parse_json_response
from app.tools.extract.dom_extract import collect_visible_dom


class AITextTool(BaseTool):

    name = "ai_text"

    description = "AI自动识别并提取文本"

    parameters = {
        "task": "string"
    }

    async def execute(self, context, **kwargs):

        task = kwargs.get("task")

        try:

            dom = await collect_visible_dom(context.page)

            resolver = SelectorResolver()
            result = await resolver.resolve(task, dom, platform=getattr(context, "platform", None))

            if not result:
                return ToolResult(
                    success=False,
                    error="AI selector resolution failed"
                )

            data = parse_json_response(result)
            selector = data["selector"]

            text = await context.page.locator(selector).inner_text()

            return ToolResult(
                success=True,
                data={
                    "text": text,
                    "selector": selector,
                    "reason": data.get("reason"),
                }
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )
