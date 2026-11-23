from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from playwright.async_api import BrowserContext, Page

from .models import SessionState

if TYPE_CHECKING:
    from app.platforms.base import PlatformProfile
    from app.core.executor import ToolExecutor


@dataclass
class BrowserSession:
    '''
        每个Agent的会话信息
    '''

    session_id: str

    state: SessionState = SessionState.CREATED

    context: Optional[BrowserContext] = None

    page: Optional[Page] = None

    current_url: str = ""

    platform: Optional["PlatformProfile"] = None

    executor: Optional["ToolExecutor"] = None

    variables: dict = field(default_factory=dict)

    results: list[dict] = field(default_factory=list)
