from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import TaskRuntime, TaskSpec, TaskView


class BackgroundTaskStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def task_dir(self, task_id: str) -> Path:
        return self.base_dir / task_id

    def output_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "output.txt"

    def create(self, spec: TaskSpec) -> None:
        d = self.task_dir(spec.id)
        d.mkdir(parents=True, exist_ok=True)
        self.write_json(d / "spec.json", spec.to_dict())
        self.write_runtime(spec.id, TaskRuntime())
        self.output_path(spec.id).write_text("", encoding="utf-8")

    def read_spec(self, task_id: str) -> TaskSpec:
        return TaskSpec.from_dict(self.read_json(self.task_dir(task_id) / "spec.json"))

    def read_runtime(self, task_id: str) -> TaskRuntime:
        return TaskRuntime.from_dict(self.read_json(self.task_dir(task_id) / "runtime.json"))

    def write_runtime(self, task_id: str, runtime: TaskRuntime) -> None:
        self.write_json(self.task_dir(task_id) / "runtime.json", runtime.to_dict())

    def append_output(self, task_id: str, text: str) -> None:
        with self.output_path(task_id).open("a", encoding="utf-8") as f:
            f.write(text)

    def read_output(self, task_id: str, offset: int = 0) -> tuple[str, int]:
        text = self.output_path(task_id).read_text(encoding="utf-8")
        chunk = text[offset:]
        return chunk, len(text)

    def list_views(self) -> List[TaskView]:
        views: List[TaskView] = []
        for d in sorted(self.base_dir.iterdir()):
            if not d.is_dir() or not (d / "spec.json").exists():
                continue
            task_id = d.name
            views.append(TaskView(self.read_spec(task_id), self.read_runtime(task_id)))
        return views

    @staticmethod
    def read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write_json(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
