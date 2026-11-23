from app.agents.llm_client import chat
from app.agents.json_utils import parse_json_response
from app.platforms.base import PlatformProfile


class DomAnalyzer:

    async def extract_links(
        self,
        task: str,
        dom: list,
        platform: PlatformProfile | None = None,
        limit: int = 10,
    ) -> list[dict]:

        platform_section = self._build_platform_section(platform)

        prompt = f"""
你是一个网页数据提取专家。
{platform_section}
根据用户任务，从 DOM 中识别符合条件的链接列表。

要求：
1. 只返回与任务真正相关的链接，过滤导航、帮助、blog、popular、about 等非目标链接
2. 优先返回帖子详情、博主主页、商品详情、内容详情等业务链接
3. 最多返回 {limit} 条
4. url 必须是完整可访问链接

用户任务：
{task}

DOM结构（含 tag / text / href / ariaLabel / role / testId）：
{dom}

请只返回 JSON，不要 markdown：
{{
  "links": [
    {{"url": "https://...", "label": "显示文本或用户名", "reason": "为何选中"}}
  ]
}}
"""
        text = await chat(prompt)
        if not text:
            return []

        data = parse_json_response(text)
        links = data.get("links", []) if isinstance(data, dict) else []

        results = []
        for item in links[:limit]:
            url = item.get("url")
            if not url:
                continue
            results.append({
                "url": url,
                "label": item.get("label", ""),
                "reason": item.get("reason", ""),
                "text": item.get("label", ""),
            })

        return results

    async def extract_data(
        self,
        task: str,
        dom: list,
        platform: PlatformProfile | None = None,
    ) -> dict:

        platform_section = self._build_platform_section(platform)

        prompt = f"""
你是一个网页数据提取专家。
{platform_section}
根据用户任务，从 DOM 中提取结构化数据。

用户任务：
{task}

DOM结构：
{dom}

请只返回 JSON，不要 markdown。字段名使用英文 snake_case，只包含任务需要的字段。
示例：
{{
  "data": {{
    "username": "xxx",
    "display_name": "显示名",
    "bio": "简介"
  }}
}}
"""
        text = await chat(prompt)
        if not text:
            return {}

        parsed = parse_json_response(text)
        if isinstance(parsed, dict) and "data" in parsed:
            return parsed["data"]
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _build_platform_section(self, platform: PlatformProfile | None) -> str:
        if not platform:
            return "当前为通用网页场景。"

        return f"""
当前站点: {platform.name}
站点类型: {platform.category}
站点提示: {platform.category_hints()}
已知 selector 参考:
{platform.selector_hints() or "（暂无）"}
"""
