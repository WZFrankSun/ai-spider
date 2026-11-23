import asyncio
import sys

from app.browser.browser_manager import BrowserManager
from app.bootstrap import create_platform_session, create_executor
from app.workflows.crawl_list import crawl_list, default_export_path

PLATFORM = "shopify"


async def main():

    shop_url = sys.argv[1] if len(sys.argv) > 1 else ""
    if not shop_url:
        print("usage: python examples/ecommerce/test_shopify_crawl.py https://your-store.com/collections/all")
        return

    bm = BrowserManager()
    await bm.start()

    executor = create_executor()
    session, platform = await create_platform_session(bm, PLATFORM, executor=executor)

    slug = shop_url.rstrip("/").split("/")[-1] or "shop"
    export_path = default_export_path(PLATFORM, slug)

    try:
        results = await crawl_list(
            executor,
            session,
            seed_url=shop_url,
            mode="list_only",
            list_page_type="collection",
            limit=20,
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
