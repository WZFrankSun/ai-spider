import asyncio

from app.browser.browser_manager import BrowserManager
from app.core.registry import ToolRegistry
from app.core.executor import ToolExecutor

from app.tools.browser.goto import GotoTool
from app.tools.ai.ai_click import AIClickTool
from app.tools.ai.ai_text import AITextTool


async def main():

    bm = BrowserManager()
    await bm.start()

    session = await bm.create_session()

    registry = ToolRegistry()

    registry.register(GotoTool)
    registry.register(AIClickTool)
    registry.register(AITextTool)

    executor = ToolExecutor(registry)

    # 1. 打开网页
    await executor.execute(
        "goto",
        session,
        url="https://www.baidu.com"
    )

    # 2. AI提取文本（自然语言）
    result = await executor.execute(
        "ai_text",
        session,
        task="提取页面标题"
    )

    print("AI TEXT:", result.data)

    #3. AI点击（自然语言）
    result2 = await executor.execute(
        "ai_click",
        session,
        task="点击页面中的百度一下按钮（如果存在）"
    )

    print("AI CLICK:", result2.data)

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())