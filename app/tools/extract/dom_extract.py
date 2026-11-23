VISIBLE_DOM_SCRIPT = """
(limit) => {
    const isVisible = (el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        const style = window.getComputedStyle(el);
        return style.visibility !== "hidden" && style.display !== "none";
    };

    const toItem = (el) => ({
        tag: el.tagName,
        text: (el.innerText || "").slice(0, 80),
        id: el.id || null,
        className: el.className || null,
        ariaLabel: el.getAttribute("aria-label"),
        role: el.getAttribute("role"),
        testId: el.getAttribute("data-testid"),
        href: el.tagName === "A" ? el.href : null,
    });

    const isUseful = (item) =>
        item.text || item.id || item.ariaLabel || item.testId || item.href;

    const result = [];
    const seenHrefs = new Set();

    // 优先收集可见链接，避免 SPA 页面深层 wrapper 占满 limit 导致帖子链接被截断
    for (const el of document.querySelectorAll("a[href]")) {
        if (result.length >= limit) break;
        if (!isVisible(el)) continue;

        const item = toItem(el);
        if (!isUseful(item)) continue;
        if (seenHrefs.has(item.href)) continue;

        seenHrefs.add(item.href);
        result.push(item);
    }

    for (const el of document.querySelectorAll("body *")) {
        if (result.length >= limit) break;
        if (el.tagName === "A") continue;
        if (!isVisible(el)) continue;

        const item = toItem(el);
        if (!isUseful(item)) continue;

        result.push(item);
    }

    return result;
}
"""


async def collect_visible_dom(page, limit: int = 300) -> list:
    return await page.evaluate(VISIBLE_DOM_SCRIPT, limit)
