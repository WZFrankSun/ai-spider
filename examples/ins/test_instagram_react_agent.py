import asyncio

from app.browser.browser_manager import BrowserManager
from app.bootstrap import create_platform_session, create_executor
from app.agents.react_agent import ReActAgent
from app.workflows.crawl_list import default_export_path

PLATFORM = "instagram"
SEED_URL = "https://www.instagram.com/explore/tags/Wohnm%C3%B6bel/"
LIMIT = 5


async def main():

    bm = BrowserManager()
    await bm.start()

    executor = create_executor()
    session, platform = await create_platform_session(bm, PLATFORM, executor=executor)

    agent = ReActAgent(executor)
    export_path = default_export_path(PLATFORM, "Wohnmoebel")

#     task = f"""
# 在 Instagram 上批量采集标签页博主信息（platform={PLATFORM}）：

# 1. ensure_auth 确保已登录
# 2. 打开 {SEED_URL}
# 3. wait 等待页面加载完成
# 4. scroll 向下滚动加载更多帖子（y=1200，可重复 2 次）
# 5. ai_extract_links 用 LLM 理解 DOM，提取 {LIMIT} 个博主主页链接
#    task="从标签页找出帖子作者或相关博主的主页链接，排除 blog/popular/explore 等导航链接"
#    store_as=profile_links, limit={LIMIT}
# 6. for_each 遍历 profile_links，对每个博主执行：
#    - goto 进入主页
#    - wait 等待 1 秒
#    - extract_page 提取 profile 页字段（page_type=profile, ai_fallback=true）
#    - save_results 保存到 results
# 7. export_results 导出到 {export_path}
# """
    task = f"""
    # 在 Instagram 上批量采集标签页博主信息（platform={PLATFORM}）：
     1. 确保已经登录
     2. 打开 https://www.instagram.com/explore/tags/Wohnm%C3%B6bel/
     3. 获得通过#Wohnmöbel搜索的结果页，提取前五个帖子的链接
     4. 分别进入每个帖子，使用ai_extract提取帖子博主名称，博主主页链接，保存到results中

    """
    history = await agent.run(task, session, max_steps=15)

    print("\n🎯 FINAL HISTORY:", history)
    print(f"\n📦 PLATFORM: {platform.name} ({platform.category})")
    print(f"\n📦 RESULTS ({len(session.results)}):")
    for item in session.results:
        print(f"  - {item}")

    if session.results:
        print(f"\n📁 导出路径: {export_path}")

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())
