#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WEBUI="$ROOT/webui"
STATIC="$ROOT/src/whale_cli/web/static"
TUTORIALS="$ROOT/src/whale_cli/web/tutorials"

if [ ! -d "$WEBUI/node_modules" ]; then
  npm --prefix "$WEBUI" ci
fi

npm --prefix "$WEBUI" run build
mkdir -p "$STATIC" "$TUTORIALS"
find "$STATIC" -mindepth 1 -delete
find "$TUTORIALS" -mindepth 1 -delete
cp -R "$WEBUI/dist/." "$STATIC/"
cp -R "$ROOT/docs/新手入门/." "$TUTORIALS/"

printf 'Packaged WebUI: %s\n' "$STATIC"
printf 'Packaged tutorials: %s\n' "$TUTORIALS"
