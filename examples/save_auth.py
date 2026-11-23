import asyncio
import sys

from app.browser.browser_manager import BrowserManager
from app.bootstrap import create_platform_session
from app.platforms.registry import PlatformRegistry, default_auth_path


async def main():

    platform_name = sys.argv[1] if len(sys.argv) > 1 else "instagram"
    available = PlatformRegistry.list_names()

    if platform_name not in available:
        print(f"unsupported platform: {platform_name}")
        print(f"usage: python examples/save_auth.py [{'|'.join(available)}]")
        return

    platform = PlatformRegistry.load(platform_name)
    auth_path = default_auth_path(platform_name)

    if not platform.login_url:
        print(f"platform {platform_name} does not require login")
        return

    bm = BrowserManager(headless=False)
    await bm.start()

    session, _ = await create_platform_session(bm, platform_name)

    await session.page.goto(platform.login_url)

    print(f"请在打开的浏览器中手动登录 {platform_name}。")
    print("登录完成后回到终端，按 Enter 保存登录态...")
    input()

    await bm.save_storage_state(session.session_id, str(auth_path))

    print(f"登录态已保存: {auth_path}")

    await bm.close_session(session.session_id)


if __name__ == "__main__":

    asyncio.run(main())
