from app.agents.dom_analyzer import DomAnalyzer
from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.tools.extract.dom_extract import collect_visible_dom
from app.tools.extract.field_extract import extract_fields


class ExtractPageTool(BaseTool):

    name = "extract_page"

    description = "按平台 YAML 提取字段；字段缺失时可由 LLM 理解 DOM 补充"

    parameters = {
        "page_type": "string",
        "store_as": "string",
        "task": "string",
        "use_ai": "boolean",
        "ai_fallback": "boolean",
    }

    async def execute(self, context, **kwargs):

        page_type = kwargs.get("page_type")
        store_as = kwargs.get("store_as", "last_item")
        task = kwargs.get("task")
        use_ai = bool(kwargs.get("use_ai"))
        ai_fallback = kwargs.get("ai_fallback", True)

        platform = getattr(context, "platform", None)
        if not platform:
            return ToolResult(success=False, error="session.platform is required")

        if not page_type:
            page_type = platform.extraction.get("default_page_type")

        if not page_type:
            return ToolResult(success=False, error="page_type is required")

        schema = platform.get_page_schema(page_type)
        fields = schema.get("fields", {})

        if not fields:
            return ToolResult(
                success=False,
                error=f"no fields configured for page_type: {page_type}",
            )

        try:
            url = context.page.url
            data = await extract_fields(context.page, fields, base_url=url)
            data["page_type"] = page_type
            data["platform"] = platform.name
            had_regex_values = any(data.get(key) for key in fields)
            source = "regex"

            should_use_ai = use_ai or (
                ai_fallback is not False and self._needs_ai_enrichment(data, fields)
            )

            if should_use_ai:
                if not task:
                    field_names = ", ".join(fields.keys())
                    task = f"从当前 {page_type} 页面提取字段: {field_names}"

                dom = await collect_visible_dom(context.page, limit=400)
                ai_data = await DomAnalyzer().extract_data(
                    task,
                    dom,
                    platform=platform,
                )
                data = self._merge_data(data, ai_data)
                source = "hybrid" if had_regex_values else "llm"

            data["source"] = source
            context.variables[store_as] = data
            context.variables["url"] = url

            return ToolResult(
                success=True,
                data=data,
                message="page extracted",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _needs_ai_enrichment(self, data: dict, fields: dict) -> bool:
        for key in fields:
            value = data.get(key)
            if value is None or value == "":
                return True
        return False

    def _merge_data(self, base: dict, extra: dict) -> dict:
        merged = dict(base)
        for key, value in extra.items():
            if value is None or value == "":
                continue
            if not merged.get(key):
                merged[key] = value
        return merged
