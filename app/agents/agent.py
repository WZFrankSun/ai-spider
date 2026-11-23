from app.agents.planner import Planner


class Agent:

    def __init__(self, executor):

        self.executor = executor

        self.planner = Planner(executor.registry)

    async def run(self, task: str, session):

        plan = await self.planner.plan(task)

        print("\n📋 PLAN:", plan)

        results = []

        for step in plan:

            tool = step["tool"]

            args = step.get("args", {})

            print(f"\n🚀 EXECUTE: {tool} -> {args}")

            result = await self.executor.execute(
                tool,
                session,
                **args
            )

            print(f"📦 RESULT: {result}")

            results.append(result)

        return results
