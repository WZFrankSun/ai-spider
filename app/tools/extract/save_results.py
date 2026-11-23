from app.core.tool import BaseTool
from app.core.result import ToolResult


class SaveResultsTool(BaseTool):

    name = "save_results"

    description = "将提取结果追加到 session.results"

    parameters = {
        "data_key": "string",
    }

    async def execute(self, context, **kwargs):

        data_key = kwargs.get("data_key", "last_item")
        data = context.variables.get(data_key)

        if not data:
            return ToolResult(
                success=False,
                error=f"no data found for key: {data_key}",
            )

        if isinstance(data, dict):
            context.results.append(data)
        elif isinstance(data, list):
            context.results.extend(data)
        else:
            context.results.append({"value": data})

        return ToolResult(
            success=True,
            data={
                "saved": data,
                "total": len(context.results),
            },
            message="results saved",
        )
