from app.agents.dom_analyzer import DomAnalyzer
from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.tools.extract.dom_extract import collect_visible_dom
from app.tools.extract.link_filter import filter_links, merge_links

EXTRACT_LINKS_SCRIPT = """
() => {
    const results = [];
    for (const el of document.querySelectorAll("a[href]")) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        results.push({
            href: el.href,
            text: (el.innerText || "").slice(0, 80),
        });
    }
    return results;
}
"""


class ExtractLinksTool(BaseTool):

    name = "extract_links"

    description = "从当前页面提取链接；支持 YAML 规则过滤，并可由 LLM 理解 DOM 补充或替代"

    parameters = {
        "pattern": "string",
        "selector": "string",
        "limit": "number",
        "store_as": "string",
        "task": "string",
        "use_ai": "boolean",
        "ai_fallback": "boolean",
    }

    async def execute(self, context, **kwargs):

        pattern_name = kwargs.get("pattern")
        limit = int(kwargs.get("limit") or 10)
        store_as = kwargs.get("store_as", "links")
        selector = kwargs.get("selector")
        task = kwargs.get("task")
        use_ai = bool(kwargs.get("use_ai"))
        ai_fallback = kwargs.get("ai_fallback", True)

        platform = getattr(context, "platform", None)
        if not pattern_name and platform:
            pattern_name = platform.extraction.get("default_link_pattern")

        try:
            if selector:
                raw_links = await context.page.eval_on_selector_all(
                    selector,
                    "els => els.map(el => ({href: el.href, text: (el.innerText || '').slice(0, 80)}))",
                )
            else:
                raw_links = await context.page.evaluate(EXTRACT_LINKS_SCRIPT)

            pattern_config = {}
            if platform and pattern_name:
                pattern_config = platform.extraction.get("link_patterns", {}).get(pattern_name, {})

            regex_links = filter_links(raw_links, pattern_config, limit)
            links = regex_links
            source = "regex"

            should_use_ai = use_ai or (
                ai_fallback is not False and len(links) < limit
            )

            if should_use_ai:
                if not task:
                    task = (
                        f"从当前页面找出与「{pattern_name or '目标'}」相关的业务链接，"
                        f"排除导航/帮助/blog/popular 等非目标链接，最多 {limit} 条"
                    )

                dom = await collect_visible_dom(context.page, limit=500)
                ai_links = await DomAnalyzer().extract_links(
                    task,
                    dom,
                    platform=platform,
                    limit=limit,
                )
                links = merge_links(regex_links, ai_links, limit)
                source = "hybrid" if regex_links else "llm"

            context.variables[store_as] = links

            return ToolResult(
                success=True,
                data={
                    "pattern": pattern_name,
                    "count": len(links),
                    "links": links,
                    "store_as": store_as,
                    "source": source,
                },
                message="links extracted",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
