from copy import deepcopy

from app.core.tool import BaseTool
from app.core.result import ToolResult


def _render_value(value, item: dict, index: int):
    if isinstance(value, str):
        rendered = value.replace("{{index}}", str(index))
        for key, val in item.items():
            rendered = rendered.replace(f"{{{{item.{key}}}}}", str(val))
        return rendered

    if isinstance(value, dict):
        return {key: _render_value(val, item, index) for key, val in value.items()}

    if isinstance(value, list):
        return [_render_value(val, item, index) for val in value]

    return value


class ForEachTool(BaseTool):

    name = "for_each"

    description = "遍历 variables 中的列表，对每一项依次执行多个工具步骤"

    parameters = {
        "items_key": "string",
        "steps": "array",
        "limit": "number",
        "delay_ms": "number",
        "save_key": "string",
    }

    async def execute(self, context, **kwargs):

        executor = getattr(context, "executor", None)
        if not executor:
            return ToolResult(
                success=False,
                error="session.executor is required for for_each",
            )

        items_key = kwargs.get("items_key", "links")
        steps = kwargs.get("steps") or []
        limit = int(kwargs.get("limit") or 10)
        delay_ms = int(kwargs.get("delay_ms") or 0)
        save_key = kwargs.get("save_key", "last_item")

        items = context.variables.get(items_key, [])[:limit]
        processed = []

        for index, item in enumerate(items):
            context.variables["item"] = item
            context.variables["item_index"] = index

            for step in steps:
                tool = step.get("tool")
                args = _render_value(deepcopy(step.get("args", {})), item, index)

                result = await executor.execute(tool, context, **args)

                if not result.success:
                    return ToolResult(
                        success=False,
                        error=result.error,
                        data={
                            "processed": processed,
                            "failed_index": index,
                            "failed_tool": tool,
                        },
                    )

            saved = context.variables.get(save_key)
            if saved:
                processed.append(saved)

            if delay_ms:
                await context.page.wait_for_timeout(delay_ms)

        context.variables[f"{items_key}_processed"] = processed

        return ToolResult(
            success=True,
            data={
                "count": len(processed),
                "results": processed,
            },
            message="for_each completed",
        )
