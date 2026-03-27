#!/bin/zsh

set -e

REPO_DIR="/Volumes/6000-Projects/6300-Apps/hover-frame-extractor"

cd "$REPO_DIR"
source .venv/bin/activate
drone-frame-extractor ui "$@"
