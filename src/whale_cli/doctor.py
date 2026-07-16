"""Deployment diagnostics for Whale CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any

from whale_cli.runtime import resolve_runtime_paths


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


def collect_checks(*, require_web: bool = False) -> dict[str, Any]:
    paths = resolve_runtime_paths()
    paths.ensure_writable_directories()
    api_key_present = any(os.environ.get(name) for name in ("STEP_API_KEY", "OPENAI_API_KEY", "MOONSHOT_API_KEY"))
    if not api_key_present and paths.config_file.is_file():
        try:
            config = json.loads(paths.config_file.read_text(encoding="utf-8"))
            api_key_present = bool((config.get("llm") or {}).get("api_key"))
        except (OSError, ValueError, AttributeError):
            pass

    checks = [
        Check("python", "ok" if sys.version_info >= (3, 10) else "fail", sys.version.split()[0]),
        Check("home", "ok" if os.access(paths.home, os.W_OK) else "fail", str(paths.home)),
        Check("workspace", "ok" if os.access(paths.workspace, os.W_OK) else "fail", str(paths.workspace)),
        Check(
            "api_key",
            "ok" if api_key_present else "warn",
            str(paths.config_file),
            required=False,
        ),
        Check(
            "web_static",
            "ok" if (paths.static_root / "index.html").is_file() else ("fail" if require_web else "warn"),
            str(paths.static_root),
            required=require_web,
        ),
        Check(
            "tutorials",
            "ok" if paths.tutorials_root.is_dir() else "warn",
            str(paths.tutorials_root),
            required=False,
        ),
    ]
    healthy = all(item.status != "fail" for item in checks if item.required)
    return {
        "status": "ok" if healthy else "fail",
        "paths": {key: str(value) for key, value in asdict(paths).items()},
        "checks": [asdict(item) for item in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether Whale CLI is ready to run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--web", action="store_true", help="Require a built WebUI.")
    args = parser.parse_args()
    report = collect_checks(require_web=args.web)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Whale doctor: {report['status'].upper()}")
        for item in report["checks"]:
            print(f"  [{item['status'].upper():4}] {item['name']}: {item['detail']}")
    raise SystemExit(0 if report["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
