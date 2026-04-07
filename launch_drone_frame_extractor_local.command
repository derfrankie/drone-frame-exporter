#!/bin/zsh

set -e

SCRIPT_DIR=${0:A:h}
REPO_DIR="$SCRIPT_DIR"

cd "$REPO_DIR"
exec "$REPO_DIR/.venv/bin/python" "$REPO_DIR/run_app.py" ui "$@"
