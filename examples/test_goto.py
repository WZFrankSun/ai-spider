import asyncio

from app.core.registry import ToolRegistry
from app.core.executor import ToolExecutor

from app.browser.browser_manager import BrowserManager
from app.tools.browser.goto import GotoTool
from app.tools.browser.html import HtmlTool


async def main():

    # 1. browser
    bm = BrowserManager()
    await bm.start()

    session = await bm.create_session()

    # 2. tool system
    registry = ToolRegistry()
    registry.register(GotoTool)
    registry.register(HtmlTool)

    executor = ToolExecutor(registry)

    # 3. execute tool
    result = await executor.execute(
        tool_name = "goto",
        context=session,
        url="https://www.baidu.com"
    )
    print("RESULT:", result)

    # 5. html
    r3 = await executor.execute(
        "html",
        context = session
    )
    print("HTML:", r3.data["html"])

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())