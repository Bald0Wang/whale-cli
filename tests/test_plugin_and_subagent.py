from whale_cli.plugin import load_plugin_tools
from whale_cli.soul.approval import Approval
from whale_cli.tools.agent import AgentTool

from .conftest import make_tool_call


def test_load_plugin_tools(tmp_path):
    plugin_dir = tmp_path / "plugins" / "echo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text('{"entry": "tool.py:EchoTool"}', encoding="utf-8")
    (plugin_dir / "tool.py").write_text(
        "from whale_cli.tools.base import Tool, ok\n"
        "class EchoTool(Tool):\n"
        "    name='PluginEcho'\n"
        "    description='Echo from plugin'\n"
        "    schema={'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object'}}}\n"
        "    def __call__(self, text=''):\n"
        "        return ok('plugin:' + text)\n",
        encoding="utf-8",
    )

    tools = load_plugin_tools(tmp_path / "plugins")
    assert [t.name for t in tools] == ["PluginEcho"]
    assert tools[0](text="ok")["stdout"] == "plugin:ok"


def test_agent_tool_runs_subagent_with_fresh_context(mock_llm, tmp_workspace):
    llm = mock_llm([
        [make_tool_call("sub_call", "Bash", {"command": "echo child"})],
        "subagent summary child",
    ])
    tool = AgentTool(llm=llm, approval=Approval(yolo=True), max_steps=3)
    result = tool(description="inspect", prompt="run echo child", agent_type="coder")

    assert result["exit_code"] == 0
    assert "subagent summary child" in result["stdout"]
    # The subagent made its own LLM calls; parent messages were not needed.
    assert len(llm.calls) == 2
