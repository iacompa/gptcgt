# Staging Web Smoke Gate

Use this gate to validate the deployed staging web experience in a real browser after deploys. Unlike the local Playwright suite, this path hits the live staging site and the live staging API without route mocks.

## What It Covers

The live browser spec at `web/tests/staging/live.spec.ts` checks:

- unauthenticated `/dashboard/chat` redirects to `/auth`
- authenticated `/dashboard/chat` loads the real workspace chat surface, including model selection and the composer
- `/dashboard/hub` reflects the real GitHub connection state for the staging smoke account

This gate is intentionally non-destructive:

- it does not create Stripe sessions
- it does not start a Hub run
- it does not disconnect GitHub
- it does not spend LLM credits
- it does not seed or mutate conversation state

## Required Secrets

Configure these GitHub Actions secrets for `.github/workflows/staging-web-smoke.yml`:

- `STAGING_WEB_BASE_URL`
  Example: `https://gptcgt.ai`
- `STAGING_WEB_SESSION_COOKIE`
  A valid `gptcgt_session` cookie value for the staging smoke user

Optional reporting/alerting secrets:

- `STAGING_SMOKE_ALERT_WEBHOOK_URL`
  Receives a JSON payload when the browser smoke fails.
- `STAGING_WEB_SMOKE_HEARTBEAT_URL`
  Pinged on successful browser smoke completion.
- `STAGING_WEB_SMOKE_FAILURE_HEARTBEAT_URL`
  Optional separate ping target for failed browser smoke runs.

## Manual Workflow Inputs

- `expect_github_connected`
  When `true`, the smoke expects the live dashboard Hub route to show the connected GitHub surface. When `false`, it expects the connect CTA instead.

## Local Usage

```bash
cd web
npm ci
npx playwright install chromium
export STAGING_WEB_BASE_URL="https://gptcgt.ai"
export STAGING_WEB_SESSION_COOKIE="..."
export STAGING_WEB_EXPECT_GITHUB_CONNECTED=true
npm run test:e2e:staging
```

## Guardrails

- Use a staging-only session cookie.
- Use a disposable staging account with billing access disabled if possible; this gate does not need billing mutations.
- Keep GitHub connection expectations aligned with the chosen staging smoke account.
- If the browser gate fails while the API gate passes, treat it as a real web-shipping problem rather than a transient test mismatch.
- The workflow always publishes a GitHub Actions step summary now, even if the browser smoke fails.
