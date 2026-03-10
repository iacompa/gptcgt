#!/bin/bash
set -eo pipefail

echo "=== Deploying to Staging Environment ==="

if [[ -z "$(command -v flyctl)" ]]; then
    echo "Error: flyctl not found. Please install the Fly.io CLI."
    exit 1
fi

APP_NAME="gptcgt-staging"

echo "Deploying API to $APP_NAME..."
flyctl deploy --config fly.staging.toml --app "$APP_NAME"

echo "Done! Staging is live at https://$APP_NAME.fly.dev"
