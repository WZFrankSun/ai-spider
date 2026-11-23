from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.agents.dom_analyzer import DomAnalyzer
from app.platforms.base import PlatformProfile
from app.tools.extract.dom_extract import collect_visible_dom


async def _wait_for_dynamic_content(page, platform: PlatformProfile | None) -> None:
    selector = platform.resolve_content_selector(page.url) if platform else None

    if selector:
        try:
            await page.wait_for_selector(selector, timeout=15000)
            await page.wait_for_timeout(1000)
            return
        except Exception:
            pass

    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    await page.wait_for_timeout(2000)


class AIExtractLinksTool(BaseTool):

    name = "ai_extract_links"

    description = "用 LLM 理解 DOM，按自然语言任务提取相关链接列表"

    parameters = {
        "task": "string",
        "limit": "number",
        "store_as": "string",
    }

    async def execute(self, context, **kwargs):

        task = kwargs.get("task")
        limit = int(kwargs.get("limit") or 10)
        store_as = kwargs.get("store_as", "items")

        if not task:
            return ToolResult(success=False, error="task is required")

        try:
            platform = getattr(context, "platform", None)
            await _wait_for_dynamic_content(context.page, platform)

            dom = await collect_visible_dom(context.page, limit=500)
            analyzer = DomAnalyzer()
            links = await analyzer.extract_links(
                task,
                dom,
                platform=platform,
                limit=limit,
            )

            context.variables[store_as] = links

            return ToolResult(
                success=True,
                data={
                    "count": len(links),
                    "links": links,
                    "store_as": store_as,
                    "source": "llm",
                },
                message="ai links extracted",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
