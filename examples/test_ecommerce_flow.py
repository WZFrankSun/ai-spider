import asyncio
import sys

from app.browser.browser_manager import BrowserManager
from app.bootstrap import create_platform_session, create_executor
from app.platforms.registry import PlatformRegistry

PLATFORM = sys.argv[1] if len(sys.argv) > 1 else "amazon"


async def main():

    platform = PlatformRegistry.load(PLATFORM)
    bm = BrowserManager()
    await bm.start()

    session, _ = await create_platform_session(bm, PLATFORM)
    executor = create_executor()

    search_input = platform.get_selector("search_input")
    search_button = platform.get_selector("search_button")

    if PLATFORM == "amazon":
        await executor.execute("goto", session, url=platform.home_url)
        await executor.execute("wait", session, state="domcontentloaded", timeout=15000)

        if search_input:
            await executor.execute(
                "ai_fill",
                session,
                selector=search_input,
                text="wireless keyboard",
            )

        if search_button:
            await executor.execute(
                "ai_click",
                session,
                task=f"点击搜索按钮，优先使用 selector {search_button}",
            )

        result = await executor.execute(
            "ai_text",
            session,
            task="提取第一个搜索结果的标题",
        )
        print("FIRST RESULT:", result.data if result.success else result.error)

    elif PLATFORM == "shopify":
        shop_url = sys.argv[2] if len(sys.argv) > 2 else ""
        if not shop_url:
            print("usage: python examples/test_ecommerce_flow.py shopify https://your-store.myshopify.com")
            await bm.close_session(session.session_id)
            return

        await executor.execute("goto", session, url=shop_url)
        await executor.execute("wait", session, state="domcontentloaded", timeout=15000)

        result = await executor.execute(
            "ai_text",
            session,
            task="提取第一个商品卡片的标题",
        )
        print("FIRST PRODUCT:", result.data if result.success else result.error)

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())
