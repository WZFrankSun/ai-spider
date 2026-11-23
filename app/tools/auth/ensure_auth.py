from pathlib import Path

from app.core.tool import BaseTool
from app.core.result import ToolResult
from app.platforms.registry import PlatformRegistry, default_auth_path


class EnsureAuthTool(BaseTool):

    name = "ensure_auth"

    description = "确保目标平台已登录，未登录时跳转登录页并可等待手动登录"

    parameters = {
        "platform": "string",
        "auth_path": "string",
        "wait_seconds": "number",
    }

    async def execute(self, context, **kwargs):

        platform_name = kwargs.get("platform") or context.variables.get("platform", "instagram")
        wait_seconds = int(kwargs.get("wait_seconds") or 0)

        try:
            profile = PlatformRegistry.load(platform_name)
        except KeyError as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

        if not profile.auth_required:
            context.variables["platform"] = platform_name
            context.variables["authenticated"] = True
            return ToolResult(
                success=True,
                data={
                    "platform": platform_name,
                    "logged_in": True,
                    "auth_required": False,
                },
                message="auth not required for this platform",
            )

        auth_path = Path(kwargs.get("auth_path") or default_auth_path(platform_name))
        context.platform = profile

        try:
            await context.page.goto(profile.home_url)
            await context.page.wait_for_load_state("domcontentloaded")

            if await self._is_logged_in(context.page, profile):
                context.variables["platform"] = platform_name
                context.variables["authenticated"] = True
                return ToolResult(
                    success=True,
                    data={
                        "platform": platform_name,
                        "logged_in": True,
                        "auth_path": str(auth_path),
                    },
                    message="already logged in",
                )

            await context.page.goto(profile.login_url)
            await context.page.wait_for_load_state("domcontentloaded")

            if wait_seconds > 0:
                await context.page.wait_for_timeout(wait_seconds * 1000)

                if await self._is_logged_in(context.page, profile):
                    auth_path.parent.mkdir(parents=True, exist_ok=True)
                    await context.context.storage_state(path=str(auth_path))
                    context.variables["platform"] = platform_name
                    context.variables["authenticated"] = True
                    return ToolResult(
                        success=True,
                        data={
                            "platform": platform_name,
                            "logged_in": True,
                            "saved_auth": str(auth_path),
                        },
                        message="logged in and saved auth state",
                    )

            return ToolResult(
                success=False,
                error=(
                    f"未登录 {platform_name}。"
                    f"请先运行: python examples/save_auth.py {platform_name}"
                ),
                data={
                    "platform": platform_name,
                    "login_url": profile.login_url,
                    "auth_path": str(auth_path),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    async def _is_logged_in(self, page, profile) -> bool:

        for selector in profile.logged_in_selectors:
            if await page.locator(selector).count() > 0:
                if await page.locator(selector).first.is_visible():
                    return True

        for selector in profile.login_form_selectors:
            if await page.locator(selector).count() > 0:
                if await page.locator(selector).first.is_visible():
                    return False

        return False
