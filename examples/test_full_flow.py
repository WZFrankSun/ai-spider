import asyncio

from app.browser.browser_manager import BrowserManager

from app.core.registry import ToolRegistry
from app.core.executor import ToolExecutor

from app.tools.browser.goto import GotoTool
from app.tools.browser.scroll import ScrollTool
from app.tools.browser.html import HtmlTool
from app.tools.browser.text import TextTool


async def main():

    # 1. browser
    bm = BrowserManager()
    await bm.start()

    session = await bm.create_session()

    # 2. tools
    registry = ToolRegistry()

    registry.register(GotoTool)
    registry.register(ScrollTool)
    registry.register(HtmlTool)
    registry.register(TextTool)

    executor = ToolExecutor(registry)

    # 3. goto
    r1 = await executor.execute(
        "goto",
        session,
        url="https://example.com"
    )

    print("GOTO:", r1)

    # 4. scroll
    r2 = await executor.execute(
        "scroll",
        session,
        y=500
    )

    print("SCROLL:", r2)

    # 5. html
    r3 = await executor.execute(
        "html",
        session
    )

    print("HTML length:", len(r3.data["html"]))

    # 6. text
    r4 = await executor.execute(
        "text",
        session,
        selector="h1"
    )

    print("TEXT:", r4.data)

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())