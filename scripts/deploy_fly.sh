#!/bin/bash
set -euo pipefail

TARGET_NAME="${1:-}"
APP_NAME="${2:-}"
CONFIG_PATH="${3:-}"

if [[ -z "$TARGET_NAME" || -z "$APP_NAME" || -z "$CONFIG_PATH" ]]; then
    echo "Usage: bash scripts/deploy_fly.sh <target-name> <app-name> <config-path> [extra flyctl args...]"
    exit 1
fi

if [[ -z "$(command -v flyctl)" ]]; then
    echo "Error: flyctl not found. Please install the Fly.io CLI."
    exit 1
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "Error: Fly config not found at $CONFIG_PATH"
    exit 1
fi

shift 3

echo "=== Deploying ${TARGET_NAME} (${APP_NAME}) ==="
flyctl deploy --config "$CONFIG_PATH" --app "$APP_NAME" "$@"
echo "=== ${TARGET_NAME} deploy finished ==="
