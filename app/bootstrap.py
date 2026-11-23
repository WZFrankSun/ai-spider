from pathlib import Path
from typing import Iterable, Type

from app.browser.browser_manager import BrowserManager
from app.browser.browser_session import BrowserSession
from app.core.executor import ToolExecutor
from app.core.registry import ToolRegistry
from app.core.tool import BaseTool
from app.platforms.base import PlatformProfile
from app.platforms.registry import PlatformRegistry, default_auth_path
from app.tools.auth.ensure_auth import EnsureAuthTool
from app.tools.browser.goto import GotoTool
from app.tools.browser.go_back import GoBackTool
from app.tools.browser.screenshot import ScreenshotTool
from app.tools.browser.set_location import SetLocationTool
from app.tools.browser.scroll import ScrollTool
from app.tools.browser.wait import WaitTool
from app.tools.ai.ai_click import AIClickTool
from app.tools.ai.ai_fill import AIFillTool
from app.tools.ai.ai_text import AITextTool
from app.tools.ai.ai_extract import AIExtractTool
from app.tools.ai.ai_extract_links import AIExtractLinksTool
from app.tools.extract.extract_links import ExtractLinksTool
from app.tools.extract.extract_page import ExtractPageTool
from app.tools.extract.extract_list import ExtractListTool
from app.tools.extract.save_results import SaveResultsTool
from app.tools.extract.export_results import ExportResultsTool
from app.tools.workflow.for_each import ForEachTool

DEFAULT_TOOLS: list[Type[BaseTool]] = [
    EnsureAuthTool,
    GotoTool,
    GoBackTool,
    WaitTool,
    ScrollTool,
    ScreenshotTool,
    SetLocationTool,
    AIFillTool,
    AIClickTool,
    AITextTool,
    AIExtractTool,
    AIExtractLinksTool,
    ExtractLinksTool,
    ExtractPageTool,
    ExtractListTool,
    SaveResultsTool,
    ExportResultsTool,
    ForEachTool,
]


def register_tools(
    registry: ToolRegistry,
    tools: Iterable[Type[BaseTool]] | None = None,
) -> ToolRegistry:

    for tool_cls in tools or DEFAULT_TOOLS:
        registry.register(tool_cls)

    return registry


def create_executor(
    extra_tools: Iterable[Type[BaseTool]] | None = None,
) -> ToolExecutor:

    registry = ToolRegistry()
    register_tools(registry, DEFAULT_TOOLS)

    if extra_tools:
        register_tools(registry, extra_tools)

    return ToolExecutor(registry)


async def create_platform_session(
    bm: BrowserManager,
    platform_name: str,
    auth_dir: Path | None = None,
    executor: ToolExecutor | None = None,
) -> tuple[BrowserSession, PlatformProfile]:

    platform = PlatformRegistry.load(platform_name)
    auth_path = default_auth_path(platform_name, auth_dir)

    browser_cfg = platform.browser
    storage_state = None

    if platform.auth_required and auth_path.exists():
        storage_state = str(auth_path)

    session = await bm.create_session(
        storage_state=storage_state,
        viewport=browser_cfg.get("viewport"),
        locale=browser_cfg.get("locale", "en-US"),
        user_agent=browser_cfg.get("user_agent"),
    )

    session.platform = platform
    session.variables["platform"] = platform.name

    if executor:
        session.executor = executor

    return session, platform
