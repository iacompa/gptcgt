#!/bin/bash
set -eo pipefail

bash scripts/deploy_fly.sh staging gptcgt-staging fly.staging.toml
echo "Done! Staging API is live at https://gptcgt-staging.fly.dev"
