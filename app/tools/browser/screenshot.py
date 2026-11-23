import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.tool import BaseTool
from app.core.result import ToolResult

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def default_screenshot_dir(platform_name: str | None = None) -> Path:
    folder = platform_name or "generic"
    return PROJECT_ROOT / "examples" / "output" / "screenshots" / folder


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return stem[:80] or "page"


def _stem_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    raw = f"{parsed.netloc}{parsed.path}".strip("/")
    return _safe_stem(raw or "page")


class ScreenshotTool(BaseTool):

    name = "screenshot"

    description = "截取当前已打开的网页，并保存到本地文件夹"

    parameters = {
        "path": "string",
        "dir": "string",
        "name": "string",
        "full_page": "boolean",
        "selector": "string",
        "timeout": "number",
        "market": "string",
    }

    async def execute(self, context, **kwargs):

        page = getattr(context, "page", None)
        if page is None:
            return ToolResult(
                success=False,
                error="page is required",
            )

        try:
            url = page.url or getattr(context, "current_url", "") or ""
            output_path = self._resolve_path(context, url, kwargs)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            selector = kwargs.get("selector")
            full_page = bool(kwargs.get("full_page", False))
            timeout = int(kwargs.get("timeout") or 30000)

            await self._wait_until_ready(context, timeout)
            if await self._reject_cookies(context):
                await self._wait_until_ready(context, timeout)

            if selector:
                await page.locator(selector).screenshot(path=str(output_path))
            else:
                await page.screenshot(path=str(output_path), full_page=full_page)

            record = {
                "path": str(output_path),
                "url": url,
                "market": kwargs.get("market") or "",
                "full_page": full_page and not selector,
                "selector": selector,
            }

            shots = context.variables.setdefault("screenshots", [])
            shots.append(record)
            context.variables["screenshot_path"] = str(output_path)

            last_item = context.variables.get("last_item")
            if isinstance(last_item, dict):
                last_item.setdefault("screenshot_path", str(output_path))

            return ToolResult(
                success=True,
                data=record,
                message="screenshot saved",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    async def _wait_until_ready(self, context, timeout: int):
        page = context.page
        try:
            await page.wait_for_load_state("load", timeout=min(15000, timeout))
        except Exception:
            pass

        platform = getattr(context, "platform", None)
        selectors = []
        optional_selectors = []
        if platform is not None:
            selectors = platform.resolve_ready_selectors(page.url or "")
            optional_selectors = platform.resolve_optional_ready_selectors(page.url or "")

        for ready_selector in selectors:
            await page.locator(ready_selector).locator("visible=true").first.wait_for(
                state="visible",
                timeout=timeout,
            )

        for ready_selector in optional_selectors:
            try:
                await page.locator(ready_selector).locator("visible=true").first.wait_for(
                    state="visible",
                    timeout=min(8000, timeout),
                )
            except Exception:
                pass

        try:
            await page.wait_for_load_state("networkidle", timeout=min(8000, timeout))
        except Exception:
            pass

        await page.evaluate(
            """() => Promise.all([...document.images].filter((img) => {
                const rect = img.getBoundingClientRect();
                const inView = rect.width > 40 && rect.bottom > 0 && rect.top < window.innerHeight;
                return inView && !img.complete;
            }).map((img) => img.decode().catch(() => {})))"""
        )

    async def _reject_cookies(self, context) -> bool:
        platform = getattr(context, "platform", None)
        selector = (getattr(platform, "cookies", None) or {}).get("reject")
        if not selector:
            return False

        page = context.page
        locator = page.locator(selector).first
        if await locator.count() == 0 or not await locator.is_visible():
            return False

        await locator.click()
        try:
            await locator.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        return True

    def _resolve_path(self, context, url: str, kwargs: dict) -> Path:
        explicit = kwargs.get("path")
        if explicit:
            path = Path(explicit)
            if path.suffix.lower() not in {".png", ".jpeg", ".jpg"}:
                path = path.with_suffix(".png")
            return path

        platform = getattr(context, "platform", None)
        platform_name = getattr(platform, "name", None) or context.variables.get("platform")
        directory = Path(kwargs.get("dir") or default_screenshot_dir(platform_name))

        name = kwargs.get("name")
        stem = _safe_stem(str(name)) if name else _stem_from_url(url)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return directory / f"{stem}_{stamp}.png"
