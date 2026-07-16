from whale_cli.hooks import HookEngine, HookResult
from whale_cli.soul.toolset import Toolset
from whale_cli.tools.base import Tool, ok


class EchoTool(Tool):
    name = "Echo"
    description = "Echo text"
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object"}}}

    def __call__(self, text: str = ""):
        return ok(text)


def test_pre_tool_hook_can_block():
    hooks = HookEngine()
    hooks.on("PreToolUse", lambda payload: HookResult(action="block", reason="blocked for test"))
    ts = Toolset([EchoTool()], hook_engine=hooks)

    result = ts.handle("Echo", '{"text":"hi"}')
    assert result["exit_code"] == 125
    assert "blocked for test" in result["stderr"]


def test_post_tool_hook_observes_success():
    seen = []
    hooks = HookEngine()
    hooks.on("PostToolUse", lambda payload: seen.append(payload) or HookResult())
    ts = Toolset([EchoTool()], hook_engine=hooks)

    result = ts.handle("Echo", '{"text":"hi"}')
    assert result["exit_code"] == 0
    assert seen[0]["tool_name"] == "Echo"
    assert seen[0]["tool_output"]["stdout"] == "hi"
