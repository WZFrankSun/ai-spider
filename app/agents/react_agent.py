import copy

from app.agents.planner import Planner
from app.tools.browser.screenshot import default_screenshot_dir
from app.agents.observation import Observation
from app.agents.llm_client import chat
from app.agents.json_utils import parse_json_response

STRUCTURED_TOOLS = {
    "ensure_auth",
    "goto",
    "wait",
    "scroll",
    "screenshot",
    "set_location",
    "go_back",
    "extract_links",
    "extract_page",
    "extract_list",
    "ai_extract",
    "ai_extract_links",
    "save_results",
    "export_results",
    "for_each",
}

AI_TOOLS = {"ai_click", "ai_fill", "ai_text"}


class ReActAgent:

    def __init__(self, executor):

        self.executor = executor

        self.planner = Planner(executor.registry)

    async def run(self, task: str, session, max_steps: int = 10, max_replans: int = 2):

        session.executor = session.executor or self.executor

        history = []
        # 根据 平台 生成计划
        plan = await self.planner.plan(task, platform=session.platform)
        plan_index = 0
        step_count = 0
        replan_count = 0
        pending_step = None

        print("\n📋 INITIAL PLAN:", plan)

        while step_count < max_steps:

            if pending_step:
                step = pending_step
                pending_step = None
                print(f"\n🔁 RETRY STEP -> {step}")
            else:
                if plan_index >= len(plan):
                    print("\n📋 PLAN finished")
                    break

                planned_step = plan[plan_index]

                if self._should_skip_decide(history, planned_step):
                    step = self._adapt_step_locally(planned_step, session)
                    print(f"\n⚡ LOCAL STEP -> {step}")
                else:
                    decision = await self._decide_next_step(
                        task=task,
                        history=history,
                        planned_step=planned_step,
                    )

                    print(f"\n🧠 DECISION -> {decision}")

                    action = decision.get("action", "execute")

                    if action == "stop":
                        print("\n⏹️ STOP:", decision.get("reason"))
                        break

                    if action == "skip":
                        plan_index += 1
                        continue

                    if action == "replan":
                        if replan_count >= max_replans:
                            print("\n⏹️ STOP: max replans reached")
                            break
                        plan = await self.planner.plan(
                            task,
                            history=history,
                            platform=session.platform,
                        )
                        plan_index = 0
                        replan_count += 1
                        print("\n📋 REPLAN:", plan)
                        continue

                    step = (
                        decision
                        if action == "execute" and "tool" in decision
                        else self._adapt_step_locally(planned_step, session)
                    )

            tool = step["tool"]
            args = step.get("args", {})

            print(f"\n🚀 STEP {step_count}: {tool} -> {args}")

            result = await self.executor.execute(
                tool,
                session,
                **args
            )

            if result.success and result.data:
                self._merge_variables(session, result.data)
                if session.page:
                    session.current_url = session.page.url

            obs = Observation(
                tool=tool,
                success=result.success,
                data=result.data,
                error=result.error or ""
            )

            history.append(obs)
            step_count += 1

            print(f"👀 OBSERVATION -> {obs}")

            if self._is_done(step, result):
                print("\n✅ TASK COMPLETED")
                break

            if not result.success:
                recovery = await self._decide_after_failure(
                    task=task,
                    history=history,
                    failed_step=step,
                )

                print(f"\n🔧 RECOVERY -> {recovery}")

                recovery_action = recovery.get("action", "stop")

                if recovery_action == "stop":
                    break

                if recovery_action == "retry":
                    pending_step = recovery if recovery.get("tool") else step
                    continue

                if recovery_action == "replan":
                    if replan_count >= max_replans:
                        print("\n⏹️ STOP: max replans reached")
                        break
                    plan = await self.planner.plan(
                        task,
                        history=history,
                        platform=session.platform,
                    )
                    plan_index = 0
                    replan_count += 1
                    print("\n📋 REPLAN:", plan)
                    continue

            plan_index += 1

        return history

    def _should_skip_decide(self, history: list, planned_step: dict) -> bool:

        tool = planned_step.get("tool")

        if tool in AI_TOOLS:
            return False

        if tool not in STRUCTURED_TOOLS:
            return False

        if not history:
            return True

        return history[-1].success

    def _adapt_step_locally(self, step: dict, session) -> dict:

        adapted = copy.deepcopy(step)
        args = adapted.setdefault("args", {})
        tool = adapted.get("tool")
        platform = session.platform

        if tool == "ensure_auth" and "platform" not in args:
            args["platform"] = session.variables.get("platform", "instagram")

        if tool == "extract_links" and platform:
            args.setdefault("pattern", platform.default_link_pattern)
            args.setdefault("store_as", "items")
            if platform.category == "social":
                args.setdefault("use_ai", True)

        if tool == "extract_page" and platform:
            args.setdefault("page_type", platform.default_page_type)
            args.setdefault("store_as", "last_item")
            if platform.category == "social":
                args.setdefault("ai_fallback", True)

        if tool == "ai_extract_links" and platform:
            args.setdefault("store_as", "items")

        if tool == "ai_extract":
            args.setdefault("store_as", "last_item")

        if tool == "extract_list" and platform:
            args.setdefault("page_type", platform.default_list_page_type)
            args.setdefault("store_as", "list_items")

        if tool == "screenshot":
            platform_name = platform.name if platform else session.variables.get("platform")
            args.setdefault("dir", str(default_screenshot_dir(platform_name)))

        if tool == "save_results":
            args.setdefault("data_key", "last_item")

        if tool == "for_each" and platform:
            args.setdefault("delay_ms", int(platform.crawl.get("rate_limit_ms", 1500)))
            args.setdefault("save_key", "last_item")

        if tool in AI_TOOLS and session.variables:
            self._inject_context_hints(args, session.variables)

        return adapted

    def _inject_context_hints(self, args: dict, variables: dict):

        hints = []
        for key in ("selector", "url", "text", "username", "asin", "handle"):
            if variables.get(key):
                hints.append(f"{key}: {variables[key]}")

        if not hints:
            return

        for field in ("task",):
            if field in args and not any(h.split(":")[1].strip() in str(args[field]) for h in hints):
                args[field] = f"{args[field]}（参考: {'; '.join(hints)}）"

    def _merge_variables(self, session, data: dict):

        if not isinstance(data, dict):
            return

        reserved = {"links", "items", "count", "store_as", "results"}
        for key, value in data.items():
            if key in reserved:
                continue
            session.variables[key] = value

        if "links" in data:
            store_as = data.get("store_as", "items")
            session.variables[store_as] = data["links"]

        if "items" in data:
            store_as = data.get("store_as", "list_items")
            session.variables[store_as] = data["items"]

    async def _decide_next_step(self, task: str, history: list, planned_step: dict) -> dict:

        tools_desc = self.executor.registry.describe_tools()
        history_text = self.planner._format_history(history)

        prompt = f"""
你是一个网页自动化 Agent，采用 Observe → Decide → Act 模式。

在执行下一步之前，先根据历史结果决定如何行动。
结构化工具（extract_links/for_each/extract_page 等）已由计划生成，优先 execute，不要轻易 stop 或 replan。

用户任务：
{task}

执行历史：
{history_text or "（暂无）"}

计划执行的下一步：
{planned_step}

可用工具：
{tools_desc}

上一步的 data 可能包含 selector、url、text 等信息，应融入下一步的 args。

返回 JSON，action 只能是以下之一：
- execute: 执行（可调整 tool/args/final，必须包含 tool 和 args）
- skip: 跳过计划中的这一步
- stop: 任务已完成或无法继续
- replan: 仅当计划与页面状态严重不符时使用

请只返回 JSON，不要 markdown。
"""

        text = await chat(prompt)

        try:
            return parse_json_response(text)
        except (ValueError, TypeError) as e:
            print(e)
            return {"action": "execute", **planned_step}

    async def _decide_after_failure(
        self,
        task: str,
        history: list,
        failed_step: dict,
    ) -> dict:

        history_text = self.planner._format_history(history)

        prompt = f"""
你是一个网页自动化 Agent。

当前步骤执行失败，请决定下一步策略。优先 retry 并调整 args，不要轻易 replan。

用户任务：
{task}

执行历史：
{history_text}

失败步骤：
{failed_step}

返回 JSON，action 只能是：
- retry: 重试当前步骤（可调整 args，需包含 tool 和 args）
- replan: 根据失败原因重新规划
- stop: 无法恢复，终止任务

请只返回 JSON，不要 markdown。
"""

        text = await chat(prompt)

        try:
            return parse_json_response(text)
        except (ValueError, TypeError) as e:
            print(e)
            return {"action": "stop", "reason": "failed to parse recovery decision"}

    def _is_done(self, step, result):

        return step.get("final") and result.success
