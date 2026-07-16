#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

PYTHON=${PYTHON:-python3}
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

"$PYTHON" -m pytest
./scripts/build_web.sh
"$PYTHON" -m whale_cli.doctor --web

WHEEL_DIR=${WHEEL_DIR:-dist/release}
mkdir -p "$WHEEL_DIR"
"$PYTHON" -m pip wheel --no-deps --no-build-isolation --wheel-dir "$WHEEL_DIR" .
printf 'Release wheel written to %s\n' "$WHEEL_DIR"
