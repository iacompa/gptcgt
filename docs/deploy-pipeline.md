# Deploy And Promote Pipeline

The manual promotion workflow lives in `.github/workflows/deploy-promote.yml`.

It turns the current staging checks into a real gated promotion path:

1. deploy the Fly API to staging
2. run the staging API smoke automatically
3. run the staging web smoke automatically
4. if `promote_to_production=true`, pause at the GitHub `production` environment for manual approval
5. deploy the Fly API to production after approval

## What It Uses

- staging deploy path: `fly.staging.toml`
- production deploy path: `api/fly.toml`
- staging API smoke: `.github/workflows/staging-smoke.yml`
- staging browser smoke: `.github/workflows/staging-web-smoke.yml`

The workflow currently promotes the Fly API service. If you also deploy the proxy or web app separately, keep those deploys aligned with the same staging smoke gate before production promotion.

## Required Secrets

- `FLY_API_TOKEN`
  Required for both staging and production API deploys.
- all secrets already required by [docs/staging-smoke.md](./staging-smoke.md)
- all secrets already required by [docs/staging-web-smoke.md](./staging-web-smoke.md)

## Required GitHub Environments

Create these GitHub environments in the repository settings:

- `staging`
  Use this for visibility and optional staging-specific protections.
- `production`
  Configure required reviewers here. This is the manual approval gate before the production deploy job can start.

Without a protected `production` environment, the workflow still runs, but there is no human approval barrier.

## Manual Inputs

- `skip_checkout`
  Skip Stripe checkout creation during the staging API smoke.
- `run_webhook_smoke`
  Run the signed Stripe webhook staging smoke.
- `run_hub_smoke`
  Run a real Hub task against the configured disposable repository.
- `expect_github_connected`
  Require the staging smoke account to be GitHub-connected for both smoke suites.
- `promote_to_production`
  If `false`, the workflow stops after staging deploy plus both smokes.
  If `true`, the workflow waits for production approval and then deploys the production API.
- `hub_timeout_seconds`
  Timeout for the optional Hub smoke.

## Recommended Usage

- Normal deploys: run with `promote_to_production=false` until staging looks healthy.
- Promotion run: run with `promote_to_production=true` once the staging environment and both smoke suites are green.
- Keep `run_hub_smoke=false` for routine checks if you want faster feedback, and enable it for release candidates.
