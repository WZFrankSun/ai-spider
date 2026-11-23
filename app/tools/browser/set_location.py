import json

from app.core.tool import BaseTool
from app.core.result import ToolResult

_APPLY_API = """
async ({ postalCode, api }) => {
    const tokenEl = document.querySelector(api.token_selector);
    const token = (tokenEl && (tokenEl.content || tokenEl.value)) || "";
    const body = new URLSearchParams(api.body || {});
    body.set(api.postal_field || "zipCode", postalCode);
    const resp = await fetch(api.endpoint, {
        method: "POST",
        credentials: "include",
        headers: {
            "content-type": "application/x-www-form-urlencoded",
            "anti-csrftoken-a2z": token,
        },
        body,
    });
    return { status: resp.status, text: (await resp.text()).slice(0, 800) };
}
"""


class SetLocationTool(BaseTool):

    name = "set_location"

    description = "设置当前页面的配送邮编或地址，然后刷新页面"

    parameters = {
        "postal_code": "string",
        "dismiss": "string",
        "trigger": "string",
        "postal_input": "string",
        "submit": "string",
        "confirm": "string",
        "result": "string",
    }

    async def execute(self, context, **kwargs):

        page = getattr(context, "page", None)
        postal_code = str(kwargs.get("postal_code") or "").strip()
        if page is None:
            return ToolResult(success=False, error="page is required")
        if not postal_code:
            return ToolResult(success=False, error="postal_code is required")

        cfg = self._config(context, kwargs)
        origin = page.url

        try:
            await self._prepare_page(page, cfg)
            await self._open_and_fill(page, cfg, postal_code)

            updated = await self._wait_for_postal(page, cfg, postal_code, timeout_ms=4000)
            method = "ui"
            api_result = None

            if postal_code not in updated and cfg.get("api"):
                api_result = await page.evaluate(
                    _APPLY_API,
                    {"postalCode": postal_code, "api": cfg["api"]},
                )
                if not self._api_ok(api_result):
                    return ToolResult(
                        success=False,
                        error="failed to set postal code",
                        data={"postal_code": postal_code, "api": api_result, "location": updated},
                    )
                method = "api"
                await page.reload(wait_until="domcontentloaded")
                await self._prepare_page(page, cfg)
                updated = await self._wait_for_postal(page, cfg, postal_code)

            await self._return_to_origin(page, origin)
            if postal_code not in updated:
                await self._prepare_page(page, cfg)
                updated = await self._wait_for_postal(page, cfg, postal_code)

            if cfg.get("result") and postal_code not in updated:
                title = await page.title()
                return ToolResult(
                    success=False,
                    error=f"location was not updated to {postal_code}",
                    data={
                        "postal_code": postal_code,
                        "location": updated,
                        "method": method,
                        "url": page.url,
                        "title": title,
                    },
                )

            context.variables["postal_code"] = postal_code
            context.variables["location"] = updated
            return ToolResult(
                success=True,
                data={
                    "postal_code": postal_code,
                    "location": updated,
                    "method": method,
                    "url": page.url,
                },
                message="location updated",
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _config(self, context, kwargs: dict) -> dict:
        platform = getattr(context, "platform", None)
        cfg = dict(getattr(platform, "location", None) or {})
        reject = (getattr(platform, "cookies", None) or {}).get("reject")
        if reject:
            cfg["dismiss"] = reject
        for key in ("dismiss", "trigger", "postal_input", "submit", "confirm", "result"):
            if kwargs.get(key):
                cfg[key] = kwargs[key]
        return cfg

    async def _return_to_origin(self, page, origin: str):
        if not origin or "/dp/" not in origin or "/dp/" in page.url:
            return
        await page.goto(origin, wait_until="domcontentloaded")

    async def _prepare_page(self, page, cfg: dict):
        await self._click_if_visible(page, cfg.get("dismiss"))
        await self._pass_continue_gate(page, cfg.get("continue_selectors") or [])

    async def _wait_for_postal(self, page, cfg: dict, postal_code: str, timeout_ms: int = 8000) -> str:
        selector = cfg.get("result")
        updated = await self._location_text(page, selector)
        if not selector or postal_code in updated:
            return updated

        elapsed = 0
        while elapsed < timeout_ms:
            await page.wait_for_timeout(500)
            elapsed += 500
            await self._prepare_page(page, cfg)
            updated = await self._location_text(page, selector)
            if postal_code in updated:
                return updated
        return updated

    async def _pass_continue_gate(self, page, selectors: list):
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            if not await locator.is_visible():
                continue
            await locator.click()
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            return

    async def _open_and_fill(self, page, cfg: dict, postal_code: str):
        trigger = cfg.get("trigger")
        postal_input = cfg.get("postal_input")
        if trigger:
            trigger_box = page.locator(trigger).first
            try:
                await trigger_box.wait_for(state="visible", timeout=15000)
                await trigger_box.click(timeout=5000)
            except Exception:
                return
        if not postal_input:
            return

        box = page.locator(postal_input)
        try:
            await box.wait_for(state="visible", timeout=8000)
        except Exception:
            return
        await box.fill(postal_code)

        submit = cfg.get("submit")
        if submit:
            try:
                await page.locator(submit).click(timeout=5000)
            except Exception:
                pass

        confirm = cfg.get("confirm")
        if not confirm:
            return
        try:
            button = page.locator(confirm)
            await button.wait_for(state="visible", timeout=4000)
            await button.click()
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            return

    async def _location_text(self, page, selector: str | None) -> str:
        if not selector:
            return ""
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return ""
        return (await locator.inner_text()).strip()

    async def _click_if_visible(self, page, selector: str | None):
        if not selector:
            return
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return
        if await locator.is_visible():
            await locator.click()
            await page.wait_for_timeout(300)

    def _api_ok(self, result: dict | None) -> bool:
        if not result or result.get("status") != 200:
            return False
        try:
            data = json.loads(result.get("text") or "{}")
        except json.JSONDecodeError:
            return False
        return bool(data.get("successful") or data.get("isAddressUpdated"))
