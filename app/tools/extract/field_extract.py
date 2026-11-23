import re

from playwright.async_api import Page


async def extract_fields(page: Page, fields: dict, base_url: str | None = None) -> dict:
    data = {}

    if base_url:
        data["url"] = base_url

    for name, config in fields.items():
        value = await _extract_single_field(page, config, base_url)
        if value is not None:
            data[name] = value

    return data


async def _extract_single_field(page: Page, config, base_url: str | None):
    if isinstance(config, str):
        config = {"selector": config}

    source = config.get("source")

    if source == "url":
        if not base_url:
            return None
        regex = config.get("regex")
        if regex:
            match = re.search(regex, base_url)
            return match.group(config.get("group", 1)) if match else None
        return base_url

    selector = config.get("selector")
    if not selector:
        return None

    locator = page.locator(selector).first
    if await locator.count() == 0:
        return None

    attr = config.get("attr")
    if attr:
        return await locator.get_attribute(attr)

    text = (await locator.inner_text()).strip()
    return text or None
