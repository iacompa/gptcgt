# Staging Smoke Gate

Use the staging smoke gate to validate the live staging deployment against real external services after deploys or before public-launch changes.

For browser-level checks against the deployed staging web app, use [docs/staging-web-smoke.md](./staging-web-smoke.md).

## What It Covers

The runner at `scripts/staging_smoke.py` hits the live API and checks:

- `GET /health`
- authenticated `GET /billing/status`
- Stripe checkout session creation via `POST /billing/checkout`
- Stripe PAYG checkout creation via `POST /billing/credits`
- GitHub integration status via `GET /github/status`
- GitHub OAuth entrypoint via `GET /github/connect`
- optional signed Stripe webhook verification via `POST /billing/webhook`
- optional real Hub run execution via `POST /hub` and `GET /hub/{id}/logs`

The webhook smoke uses a signed `smoke.noop` event so it exercises signature validation and route plumbing without mutating subscription state.

## Required Secrets

Configure these GitHub Actions secrets before running `.github/workflows/staging-smoke.yml`:

- `STAGING_SMOKE_API_URL`
  Example: `https://gptcgt-staging.fly.dev`
- `STAGING_SMOKE_AUTH_TOKEN`
  A valid bearer token for a staging user with billing access. Use a disposable staging account.

Optional secrets for deeper coverage:

- `STAGING_STRIPE_WEBHOOK_SECRET`
  Required only when `run_webhook_smoke=true`
- `STAGING_SMOKE_HUB_REPO_URL`
  Required only when `run_hub_smoke=true`. This should point to a disposable GitHub repo because Hub will commit and push.
- `STAGING_SMOKE_HUB_PROMPT`
  Required only when `run_hub_smoke=true`. Keep it intentionally small and reversible.

Optional reporting/alerting secrets:

- `STAGING_SMOKE_ALERT_WEBHOOK_URL`
  Receives a JSON payload when the smoke reports failure. This is the fastest way to fan failures into Slack, PagerDuty, or another relay.
- `STAGING_API_SMOKE_HEARTBEAT_URL`
  Pinged on successful API smoke completion.
- `STAGING_API_SMOKE_FAILURE_HEARTBEAT_URL`
  Optional separate ping target for failed API smoke runs if you want an explicit failure heartbeat.

## Manual Workflow Inputs

The workflow is manual (`workflow_dispatch`) and exposes these toggles:

- `expect_github_connected`
  Fail if the smoke user is not already connected to GitHub.
- `allow_github_disconnect`
  Temporarily disconnect GitHub during the smoke run. Leave this `false` unless you are explicitly testing disconnect handling.
- `skip_checkout`
  Skip Stripe checkout-session creation if you only want auth/GitHub/Hub coverage.
- `run_webhook_smoke`
  Run the signed webhook check.
- `run_hub_smoke`
  Run a real Hub task against the configured disposable repo.
- `hub_timeout_seconds`
  Max time to wait for the Hub run before failing the smoke.

## Local Usage

You can run the same smoke locally against staging:

```bash
bash scripts/bootstrap_python_env.sh .venv-smoke
export SMOKE_API_URL="https://gptcgt-staging.fly.dev"
export SMOKE_AUTH_TOKEN="..."
export SMOKE_EXPECT_GITHUB_CONNECTED=true
export SMOKE_RUN_WEBHOOK_SMOKE=false
export SMOKE_RUN_HUB_SMOKE=false
.venv-smoke/bin/python scripts/staging_smoke.py
```

To add the optional checks:

```bash
export SMOKE_RUN_WEBHOOK_SMOKE=true
export SMOKE_STRIPE_WEBHOOK_SECRET="whsec_..."
export SMOKE_RUN_HUB_SMOKE=true
export SMOKE_HUB_REPO_URL="https://github.com/your-org/disposable-smoke-repo.git"
export SMOKE_HUB_PROMPT="Create or update STAGING_SMOKE.md with the current UTC timestamp and stop."
.venv-smoke/bin/python scripts/staging_smoke.py
```

## Guardrails

- Use a staging-only auth token, not a production token.
- Use a staging billing owner account so checkout session creation is allowed.
- Use a disposable GitHub repo for Hub smoke runs because the run will clone, commit, and push.
- Do not enable `allow_github_disconnect` unless you are prepared to reconnect the staging user manually afterward.
- The workflow always publishes a GitHub Actions step summary now, even if the smoke fails.
