import time

from whale_cli.background import BackgroundTaskManager
from whale_cli.tools.background import BackgroundListTool, BackgroundOutputTool, BackgroundStartTool


def test_background_task_lifecycle(tmp_path):
    manager = BackgroundTaskManager(tmp_path / "tasks", workspace=tmp_path)
    view = manager.start("printf bg-ok", description="print marker", cwd=str(tmp_path))

    deadline = time.time() + 3
    runtime = manager.store.read_runtime(view.spec.id)
    while runtime.status not in ("completed", "failed") and time.time() < deadline:
        time.sleep(0.05)
        runtime = manager.store.read_runtime(view.spec.id)

    assert runtime.status == "completed"
    text, _, runtime = manager.output(view.spec.id)
    assert "bg-ok" in text
    assert runtime.exit_code == 0


def test_background_tools(tmp_path):
    manager = BackgroundTaskManager(tmp_path / "tasks", workspace=tmp_path)
    start = BackgroundStartTool(manager)
    list_tool = BackgroundListTool(manager)
    output = BackgroundOutputTool(manager)

    result = start(command="printf tool-bg", description="marker")
    assert result["exit_code"] == 0
    task_id = result["stdout"].split('"task_id": "')[1].split('"')[0]
    time.sleep(0.2)
    assert task_id in list_tool()["stdout"]
    assert "tool-bg" in output(task_id=task_id)["stdout"]
