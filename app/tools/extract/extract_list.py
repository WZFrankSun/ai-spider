from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.tools.extract.field_extract import extract_fields


class ExtractListTool(BaseTool):

    name = "extract_list"

    description = "按平台 YAML page_types 配置，从当前列表页批量提取条目（适合电商搜索结果等）"

    parameters = {
        "page_type": "string",
        "limit": "number",
        "store_as": "string",
    }

    async def execute(self, context, **kwargs):

        page_type = kwargs.get("page_type")
        limit = int(kwargs.get("limit") or 10)
        store_as = kwargs.get("store_as", "list_items")

        platform = getattr(context, "platform", None)
        if not platform:
            return ToolResult(success=False, error="session.platform is required")

        if not page_type:
            page_type = platform.extraction.get("default_list_page_type")

        if not page_type:
            return ToolResult(success=False, error="page_type is required")

        schema = platform.get_page_schema(page_type)
        item_selector = schema.get("item_selector")
        fields = schema.get("fields", {})

        if not item_selector or not fields:
            return ToolResult(
                success=False,
                error=f"item_selector/fields not configured for page_type: {page_type}",
            )

        try:
            locators = context.page.locator(item_selector)
            count = min(await locators.count(), limit)
            items = []

            for index in range(count):
                item_page = context.page
                item_root = locators.nth(index)
                item_data = {"index": index}

                for name, config in fields.items():
                    if isinstance(config, str):
                        config = {"selector": config}

                    selector = config.get("selector")
                    if not selector:
                        continue

                    target = item_root.locator(selector).first
                    if await target.count() == 0:
                        continue

                    attr = config.get("attr")
                    if attr:
                        value = await target.get_attribute(attr)
                    else:
                        value = (await target.inner_text()).strip()

                    if value:
                        item_data[name] = value

                if len(item_data) > 1:
                    items.append(item_data)

            context.variables[store_as] = items

            return ToolResult(
                success=True,
                data={
                    "page_type": page_type,
                    "count": len(items),
                    "items": items,
                    "store_as": store_as,
                },
                message="list extracted",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
