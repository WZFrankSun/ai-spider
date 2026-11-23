import asyncio
import sys

from app.browser.browser_manager import BrowserManager
from app.bootstrap import create_platform_session, create_executor
from app.workflows.crawl_list import crawl_list, default_export_path

PLATFORM = "amazon"
SEARCH_URL = "https://www.amazon.com/s?k=wireless+keyboard"
LIMIT = 10


async def main():

    bm = BrowserManager()
    await bm.start()

    executor = create_executor()
    session, platform = await create_platform_session(bm, PLATFORM, executor=executor)

    export_path = default_export_path(PLATFORM, "wireless_keyboard")

    try:
        results = await crawl_list(
            executor,
            session,
            seed_url=SEARCH_URL,
            mode="list_only",
            list_page_type="search_result",
            limit=LIMIT,
            export_path=export_path,
        )

        print(f"\n✅ [{platform.category}] 共提取 {len(results)} 条商品:")
        for item in results:
            print(f"  - {item.get('title')} | {item.get('price')}")

        print(f"\n📁 已导出: {export_path}")

    except RuntimeError as e:
        print(f"\n❌ 任务失败: {e}")

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())
