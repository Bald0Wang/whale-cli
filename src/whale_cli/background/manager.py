from __future__ import annotations

import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

from ..security import WorkspaceViolation, parse_workspace_command, resolve_workspace_path, workspace_root
from .models import TaskRuntime, TaskSpec, TaskView
from .store import BackgroundTaskStore


class BackgroundTaskManager:
    """Thread-based background Bash runner with durable task state."""

    def __init__(self, base_dir: str | Path | None = None, *, workspace: str | Path | None = None):
        self.workspace = workspace_root(workspace)
        root = Path(base_dir) if base_dir else self.workspace / ".whale_cli" / "tasks"
        self.store = BackgroundTaskStore(root)
        self._processes: Dict[str, subprocess.Popen[str]] = {}

    def start(self, command: str, description: str = "", timeout_s: int = 300, cwd: str | None = None) -> TaskView:
        parse_workspace_command(command)
        command_cwd = resolve_workspace_path(cwd or self.workspace, self.workspace)
        task_id = f"bash_{uuid.uuid4().hex[:8]}"
        spec = TaskSpec(
            id=task_id,
            command=command,
            description=description or command[:80],
            cwd=str(command_cwd),
            timeout_s=timeout_s,
        )
        self.store.create(spec)
        thread = threading.Thread(target=self._run_task, args=(spec,), name=f"whale-cli-bg-{task_id}", daemon=True)
        thread.start()
        return TaskView(spec, self.store.read_runtime(task_id))

    def list(self) -> list[TaskView]:
        return self.store.list_views()

    def output(self, task_id: str, offset: int = 0) -> tuple[str, int, TaskRuntime]:
        text, next_offset = self.store.read_output(task_id, offset)
        return text, next_offset, self.store.read_runtime(task_id)

    def stop(self, task_id: str) -> bool:
        proc = self._processes.get(task_id)
        if proc is None or proc.poll() is not None:
            return False
        proc.terminate()
        runtime = self.store.read_runtime(task_id)
        runtime.status = "killed"
        runtime.finished_at = time.time()
        runtime.updated_at = runtime.finished_at
        self.store.write_runtime(task_id, runtime)
        return True

    def _run_task(self, spec: TaskSpec) -> None:
        runtime = self.store.read_runtime(spec.id)
        runtime.status = "running"
        runtime.started_at = time.time()
        runtime.updated_at = runtime.started_at
        self.store.write_runtime(spec.id, runtime)
        try:
            proc = subprocess.Popen(
                parse_workspace_command(spec.command),
                shell=False,
                cwd=spec.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._processes[spec.id] = proc
            try:
                stdout, _ = proc.communicate(timeout=spec.timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, _ = proc.communicate()
                runtime.status = "failed"
                runtime.failure_reason = f"Timed out after {spec.timeout_s}s"
            else:
                runtime.status = "completed" if proc.returncode == 0 else "failed"
            if stdout:
                self.store.append_output(spec.id, stdout)
            runtime.exit_code = proc.returncode
        except Exception as exc:
            runtime.status = "failed"
            runtime.failure_reason = str(exc)
            runtime.exit_code = 1
        finally:
            runtime.finished_at = time.time()
            runtime.updated_at = runtime.finished_at
            self.store.write_runtime(spec.id, runtime)
            self._processes.pop(spec.id, None)
