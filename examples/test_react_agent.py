import asyncio

from app.browser.browser_manager import BrowserManager

from app.core.registry import ToolRegistry
from app.core.executor import ToolExecutor

from app.tools.browser.goto import GotoTool
from app.tools.browser.scroll import ScrollTool

from app.tools.ai.ai_click import AIClickTool
from app.tools.ai.ai_text import AITextTool

from app.agents.react_agent import ReActAgent


async def main():

    bm = BrowserManager()
    await bm.start()

    session = await bm.create_session()

    registry = ToolRegistry()

    registry.register(GotoTool)
    registry.register(ScrollTool)
    registry.register(AIClickTool)
    registry.register(AITextTool)

    executor = ToolExecutor(registry)

    agent = ReActAgent(executor)

    result = await agent.run(
        "打开https://www.baidu.com,并提取标题",
        session,
        max_steps=5
    )

    print("\n🎯 FINAL HISTORY:", result)

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())