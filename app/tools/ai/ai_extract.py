from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.agents.dom_analyzer import DomAnalyzer
from app.tools.extract.dom_extract import collect_visible_dom


class AIExtractTool(BaseTool):

    name = "ai_extract"

    description = "用 LLM 理解 DOM，按自然语言任务提取结构化数据"

    parameters = {
        "task": "string",
        "store_as": "string",
    }

    async def execute(self, context, **kwargs):

        task = kwargs.get("task")
        store_as = kwargs.get("store_as", "last_item")

        if not task:
            return ToolResult(success=False, error="task is required")

        try:
            dom = await collect_visible_dom(context.page, limit=400)
            analyzer = DomAnalyzer()
            data = await analyzer.extract_data(
                task,
                dom,
                platform=getattr(context, "platform", None),
            )

            if context.page:
                data.setdefault("url", context.page.url)

            if context.platform:
                data["platform"] = context.platform.name

            context.variables[store_as] = data

            return ToolResult(
                success=True,
                data={
                    **data,
                    "store_as": store_as,
                    "source": "llm",
                },
                message="ai extract success",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
