from pathlib import Path

from app.core.executor import ToolExecutor
from app.browser.browser_session import BrowserSession


async def crawl_list(
    executor: ToolExecutor,
    session: BrowserSession,
    seed_url: str,
    *,
    mode: str = "visit_each",
    link_pattern: str | None = None,
    page_type: str | None = None,
    list_page_type: str | None = None,
    items_key: str = "items",
    limit: int = 10,
    export_path: str | None = None,
) -> list[dict]:
    """
    通用列表爬取 workflow。

    mode:
      - visit_each: 提取链接 -> 逐个访问详情页 -> extract_page
      - list_only:  在当前列表页直接 extract_list
    """

    session.executor = executor
    platform = session.platform

    if platform and platform.auth_required:
        auth = await executor.execute(
            "ensure_auth",
            session,
            platform=platform.name,
        )
        if not auth.success:
            raise RuntimeError(auth.error)

    await executor.execute("goto", session, url=seed_url)
    await executor.execute(
        "wait",
        session,
        state="domcontentloaded",
        timeout=15000,
    )

    rate_limit = 1500
    if platform:
        rate_limit = int(platform.crawl.get("rate_limit_ms", rate_limit))

    if mode == "list_only":
        page_type = page_type or (platform.extraction.get("default_list_page_type") if platform else None)
        result = await executor.execute(
            "extract_list",
            session,
            page_type=page_type,
            limit=limit,
            store_as=items_key,
        )
        if not result.success:
            raise RuntimeError(result.error)

        session.results.extend(result.data.get("items", []))

    else:
        link_pattern = link_pattern or (platform.extraction.get("default_link_pattern") if platform else None)
        page_type = page_type or (platform.extraction.get("default_page_type") if platform else None)

        links = await executor.execute(
            "extract_links",
            session,
            pattern=link_pattern,
            limit=limit,
            store_as=items_key,
        )
        if not links.success:
            raise RuntimeError(links.error)

        if not links.data.get("links"):
            return []

        loop = await executor.execute(
            "for_each",
            session,
            items_key=items_key,
            limit=limit,
            delay_ms=rate_limit,
            save_key="last_item",
            steps=[
                {"tool": "goto", "args": {"url": "{{item.url}}"}},
                {"tool": "wait", "args": {"ms": 1000}},
                {"tool": "extract_page", "args": {"page_type": page_type}},
                {"tool": "save_results", "args": {"data_key": "last_item"}},
            ],
        )
        if not loop.success:
            raise RuntimeError(loop.error)

    if export_path:
        await executor.execute("export_results", session, path=export_path)

    return session.results


def default_export_path(platform_name: str, slug: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / "examples" / "output" / f"{platform_name}_{slug}.json")
