import asyncio

from app.browser.browser_manager import BrowserManager
from app.bootstrap import create_platform_session, create_executor

PLATFORM = "instagram"


async def main():

    bm = BrowserManager()
    await bm.start()

    session, platform = await create_platform_session(bm, PLATFORM)
    executor = create_executor()

    auth = await executor.execute(
        "ensure_auth",
        session,
        platform=PLATFORM,
    )
    print("ENSURE AUTH:", auth.data if auth.success else auth.error)

    if not auth.success:
        await bm.close_session(session.session_id)
        return

    await executor.execute(
        "goto",
        session,
        url="https://www.instagram.com/explore/",
    )

    await executor.execute(
        "wait",
        session,
        state="domcontentloaded",
        timeout=15000,
    )

    result = await executor.execute(
        "ai_click",
        session,
        task="点击页面顶部的 Search 搜索图标或搜索入口",
    )
    print("AI CLICK:", result.data if result.success else result.error)

    result2 = await executor.execute(
        "ai_fill",
        session,
        task="搜索输入框",
        text="#Wohnmöbel",
    )
    print("AI FILL:", result2.data if result2.success else result2.error)

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())
