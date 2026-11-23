from app.core.registry import ToolRegistry
from app.tools.browser.goto import GotoTool


registry = ToolRegistry()

registry.register(GotoTool)

print(registry.list_tools())