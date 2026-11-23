import json
from pathlib import Path

from app.core.tool import BaseTool
from app.core.result import ToolResult


class ExportResultsTool(BaseTool):

    name = "export_results"

    description = "将 session.results 导出为 JSON 文件"

    parameters = {
        "path": "string",
    }

    async def execute(self, context, **kwargs):

        path = kwargs.get("path")

        if not path:
            return ToolResult(
                success=False,
                error="path is required",
            )

        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(context.results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            return ToolResult(
                success=True,
                data={
                    "path": str(output_path),
                    "count": len(context.results),
                },
                message="results exported",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
