from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.tools.extract.dom_extract import collect_visible_dom


class DomSnapshotTool(BaseTool):

    name = "dom_snapshot"

    description = "获取页面简化DOM结构（用于AI分析）"

    parameters = {}

    async def execute(self, context, **kwargs):

        try:

            dom = await collect_visible_dom(context.page)

            return ToolResult(
                success=True,
                data={"dom": dom},
                message="dom snapshot success"
            )

        except Exception as e:

            return ToolResult(
                success=False,
                error=str(e)
            )
