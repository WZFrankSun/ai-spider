from playwright.async_api import async_playwright


class BrowserFactory:

    '''
        浏览器工厂类
    '''

    @staticmethod
    async def create(headless: bool = True):

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=headless
        )

        return playwright, browser