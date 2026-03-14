#!/usr/bin/env bash
set -euo pipefail

STAMP_FILE="/opt/venv/.workspace-pyproject.sha256"
PYPROJECT_FILE="/workspace/pyproject.toml"

if [ -f "$PYPROJECT_FILE" ]; then
  current_hash="$(sha256sum "$PYPROJECT_FILE" | awk '{print $1}')"
  saved_hash=""

  if [ -f "$STAMP_FILE" ]; then
    saved_hash="$(cat "$STAMP_FILE")"
  fi

  if [ "$current_hash" != "$saved_hash" ]; then
    pip install -e '/workspace[dev]'
    printf '%s' "$current_hash" > "$STAMP_FILE"
  fi
fi

exec "$@"
