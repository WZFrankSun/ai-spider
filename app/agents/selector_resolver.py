from app.agents.llm_client import chat
from app.platforms.base import PlatformProfile


class SelectorResolver:

    async def resolve(
        self,
        task: str,
        dom: list,
        platform: PlatformProfile | None = None,
    ) -> str | None:

        platform_section = self._build_platform_section(platform)

        prompt = f"""
你是一个网页自动化专家。
{platform_section}
根据用户任务，从 DOM 中找出最合适的元素。优先选择可见、可交互的元素。

选择 selector 的优先级：
1. 配置中的已知 selector（若与任务匹配）
2. id（如 #productTitle）
3. aria-label（如 [aria-label="Search"]）
4. data-testid / data-e2e 等稳定 data 属性
5. role + 文本（如 button:has-text("Add to Cart")）
6. href（如 a[href="/product/"]）
7. 稳定的 class（社媒 SPA 的 class 通常不稳定，尽量避免）

用户任务：
{task}

DOM结构（含 ariaLabel / role / testId / href）：
{dom}

请只返回 JSON，不要 markdown：
{{
  "selector": "...",
  "reason": "..."
}}
"""
        return await chat(prompt)

    def _build_platform_section(self, platform: PlatformProfile | None) -> str:
        if not platform:
            return "当前为通用网页场景。"

        selector_hints = platform.selector_hints()
        selector_block = selector_hints or "（暂无预置 selector）"

        return f"""
当前站点: {platform.name}
站点类型: {platform.category}
站点提示: {platform.category_hints()}
已知 selector（优先使用）:
{selector_block}
"""
