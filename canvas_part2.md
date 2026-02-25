# Architecture Canvas (Part 2): Intelligence Routing & Security

**Purpose**: Defines the routing taxonomy, intent mapping, and proxy security model for the gptcgt platform.
**Scope**: Core Orchestrator/Router intent assignments, Fast API Key Cryptography, and Proxy Metering.
**Status**: active
**Source of truth**: `src/core/router.py`, `proxy/main.py`
**Last reviewed date**: 2024-05-24

## 1. Intent Taxonomy & Routing

The system relies on an aligned taxonomy between the `Orchestrator` (which parses user heuristics) and the `CodingRouter` (which selects the cheapest capable model for the task). 

### Heuristic Mapping
The Orchestrator maps natural language prompts into strict `TaskIntent` enumerations:
- `TaskIntent.CHAT` / `QUESTION`: Lightweight conversational queries. Routed to `QualityTier.LIGHT` or `STANDARD` models (e.g. Haiku, Flash) for fast response times and low cost.
- `TaskIntent.EDIT` / `CREATE` / `DEBUG`: Code modification and feature generation tasks. Trigger multi-agent loops and route to `QualityTier.PREMIUM` (e.g. Opus, GPT-4) when complexity > 7.
- `TaskIntent.ARCHITECT`: Top-level scaffolding and broad platform planning.

### Fallback Tiers
If the requested provider or family does not have a model locally configured that meets the required `QualityTier`, the router falls back safely to the cheapest available local model capable of fulfilling the core request, rather than throwing routing exceptions.

## 2. Fast API Key Verification

To prevent catastrophic `O(N)` scaling penalties under load, the proxy resolves API authentication inside `proxy/main.py` via `O(1)` cryptographic lookups:

1. **Client Header:** Client sends `Authorization: Bearer <API_KEY>`.
2. **Hash Projection:** The proxy runs a highly-optimized in-memory `sha256(token).hexdigest()`.
3. **Database Match:** The proxy fires a `SELECT owner_id WHERE key_hash = $1`.
4. **Resolution:** Bypasses all `AES-256-GCM` decryption routines entirely during the hot path.

Symmetrical encryption is reserved exclusively for the Control Plane (web dashboard) when keys must be actively read or rotated. Fallback encryption seeds are strictly forbidden; the backend will `Fail Closed` and halt initialization if the `ENCRYPTION_KEY` environment variable is omitted or improperly sized (64 hex characters req).

## 3. Proxy Billing Correctness

Proxy metering runs across strictly enforced HTTP 402/403 boundaries to prevent race conditions during parallel model requests.

- **402 Payment Required**: Returned linearly if `credit_cost` exceeds total real-time balance.
- **403 Forbidden**: Triggered probabilistically by the `SpendingCapService` when extrapolated token costs break the monthly USD threshold set by the user dashboard.

All billing gates execute entirely in the proxy middleware *before* establishing socket handshakes with upstream LLM providers.
