from uuid import uuid4
from pathlib import Path

from playwright.async_api import Browser

from app.browser.browser_factory import BrowserFactory
from app.browser.browser_session import BrowserSession
from app.browser.models import SessionState


class BrowserManager:
    '''
        管理 浏览器 生命周期的类
    '''

    def __init__(self, headless: bool = True):

        self.headless = headless

        self.browser: Browser | None = None # 浏览器实例

        self.playwright = None # playwright实例

        self.sessions = {} # 多个浏览器会话集合

    async def start(self):
        '''
            启动浏览器实例
        '''
        if self.browser:

            return

        self.playwright, self.browser = await BrowserFactory.create(headless=self.headless)

    async def create_session(
        self,
        storage_state: str | None = None,
        viewport: dict | None = None,
        user_agent: str | None = None,
        locale: str = "en-US",
    ):
        '''
            创建一个浏览器会话
        '''

        context_options = {"locale": locale}

        if storage_state and Path(storage_state).exists():
            context_options["storage_state"] = storage_state # 加载登录态

        if viewport:
            context_options["viewport"] = viewport # 设置浏览器窗口大小
 
        if user_agent:
            context_options["user_agent"] = user_agent # 设置浏览器用户代理

        context = await self.browser.new_context(**context_options)

        page = await context.new_page()

        session = BrowserSession(

            session_id=str(uuid4()),

            context=context,

            page=page,

            state=SessionState.READY

        )

        self.sessions[session.session_id] = session
        return session
    
    def get_session(self, session_id):
        '''
            获取一个浏览器会话
        '''
        return self.sessions.get(session_id)

    async def save_storage_state(self, session_id: str, path: str):
        '''
            保存浏览器登录态（cookies / localStorage）
        '''
        session = self.sessions.get(session_id)
        if not session:
            return

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await session.context.storage_state(path=path)
    
    async def close_session(self, session_id):
        '''
            关闭一个浏览器会话
        '''
        session = self.sessions.get(session_id)
        if not session:
            return
        await session.context.close()
        session.state = SessionState.CLOSED
        del self.sessions[session_id]

    async def close(self):
        '''
            关闭剩余会话、浏览器和 Playwright 驱动
        '''
        for session_id in list(self.sessions):
            await self.close_session(session_id)

        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
