from app.agents.llm_client import chat
from app.agents.json_utils import parse_json_response
from app.core.registry import ToolRegistry


class Planner:

    def __init__(self, registry: ToolRegistry):

        self.registry = registry

    async def plan(
        self,
        task: str,
        history: list | None = None,
        platform=None,
    ) -> list:

        tools_desc = self.registry.describe_tools()
        history_text = self._format_history(history)
        platform_hints = self._build_platform_hints(platform)

        prompt = f"""
你是一个网页爬虫任务规划器。

把用户任务拆解成可执行步骤。只能使用下面列出的工具，不要编造未注册的工具。
{platform_hints}
用户任务：
{task}
{history_text}
可用工具：
{tools_desc}

批量采集（多个详情页）推荐步骤：
1. ensure_auth（如需登录）
2. goto 打开种子页面
3. 若页面要求配送地或邮编，先 set_location；需要留存页面时调用 screenshot，图片保存到本地 screenshots 目录
4. wait + scroll 等待并加载内容
5. 提取链接（社媒 SPA 优先用 ai_extract_links 或 extract_links + use_ai=true）
6. for_each 遍历列表，在 steps 中依次 goto -> wait -> extract_page/ai_extract -> save_results
7. export_results 导出 JSON（最后一步加 final: true）

DOM 理解策略：
- 电商等结构稳定页面：extract_links / extract_page / extract_list（YAML selector）
- 社媒 SPA、动态布局：ai_extract_links / ai_extract，或 extract_* + use_ai=true + task 描述
- extract_links/extract_page 默认 ai_fallback=true，规则结果不足时自动调用 LLM 读 DOM

返回 JSON 数组。最后一步必须加 "final": true。

示例（Instagram 批量采博主，LLM 理解 DOM）：
[
  {{"tool":"ensure_auth","args":{{"platform":"instagram"}}}},
  {{"tool":"goto","args":{{"url":"https://www.instagram.com/explore/tags/xxx/"}}}},
  {{"tool":"wait","args":{{"state":"domcontentloaded","timeout":15000}}}},
  {{"tool":"scroll","args":{{"y":1200}}}},
  {{"tool":"ai_extract_links","args":{{
    "task":"从标签页找出帖子作者或相关博主的主页链接，排除 blog/popular/explore 等导航链接",
    "limit":5,
    "store_as":"profile_links"
  }}}},
  {{"tool":"for_each","args":{{
    "items_key":"profile_links",
    "limit":5,
    "delay_ms":1500,
    "steps":[
      {{"tool":"goto","args":{{"url":"{{{{item.url}}}}"}}}},
      {{"tool":"wait","args":{{"ms":1000}}}},
      {{"tool":"extract_page","args":{{"page_type":"profile","ai_fallback":true}}}},
      {{"tool":"save_results","args":{{"data_key":"last_item"}}}}
    ]
  }}}},
  {{"tool":"export_results","args":{{"path":"examples/output/result.json"}},"final":true}}
]

请只返回 JSON，不要 markdown。
"""

        text = await chat(prompt)
        plan = parse_json_response(text)
        return self._ensure_final_marker(plan)

    def _build_platform_hints(self, platform) -> str:
        if not platform:
            return ""

        return f"""
当前平台: {platform.name}（{platform.category}）
默认 link_pattern: {platform.default_link_pattern}
默认 page_type: {platform.default_page_type}
默认 list_page_type: {platform.default_list_page_type}
优先使用平台默认 pattern/page_type。
社媒类站点优先 ai_extract_links / ai_extract 或 extract_* + use_ai，让 LLM 理解 DOM。
电商类站点优先 YAML selector 的 extract_links / extract_list。
"""

    def _format_history(self, history: list | None) -> str:

        if not history:
            return ""

        lines = ["\n已执行步骤及结果（规划剩余步骤时不要重复已成功的操作）：\n"]

        for i, obs in enumerate(history):
            lines.append(
                f"步骤 {i + 1}: tool={obs.tool}, success={obs.success}, "
                f"data={obs.data}, error={obs.error}"
            )

        lines.append("")
        return "\n".join(lines)

    def _ensure_final_marker(self, plan: list) -> list:

        if not plan:
            return plan

        if not any(step.get("final") for step in plan):
            plan[-1]["final"] = True

        return plan
