**Purpose**: Historical record of Phase 9 critical bug remediation tasks across 22 files.
**Scope**: 30 specific P0-P3 bugs identified by a 4-agent audit following Phase 8.
**Status**: archive
**Source of truth**: N/A (Historical artifact)
**Last reviewed date**: 2024-05-24

# Phase 9: Critical Bug Remediation — 30 Bugs Across 22 Files

## Context
A deep 4-agent audit of the entire gptcgt codebase (70+ files) after your Phase 8 fixes revealed **30 new bugs** that were either introduced during Phase 8 editing or pre-existing issues not caught before. All 15 Phase 8 fixes were verified as PASS — this phase targets the newly discovered issues only.

**Current codebase score: 5.5/10** — down from 7.7 due to depth of this audit.
**Target after Phase 9: 8.0+/10**

## CRITICAL RULES
1. **Read each file FULLY before editing.** Many Phase 8 regressions came from editing without reading the full context.
2. **Check method signatures in BOTH the definition AND all callers** before changing either.
3. **Do NOT introduce new imports without verifying the imported symbol exists** — this caused bug N4.
4. **After every edit, mentally trace the call path** to ensure no TypeError/NameError/AttributeError at runtime.
5. **Reference CLAUDE.md** for all API contracts — it's the single source of truth for method signatures, event constructors, and conventions.

---

## GROUP A: P0 Showstoppers (Fix these FIRST — API is completely broken)

### Bug N1: `api/middleware/auth.py` — `settings` undefined (NameError)
**File:** `api/middleware/auth.py`
**Line:** 39
**Current code:**
```python
payload = jwt.decode(token, key=settings.jwt_secret, algorithms=["HS256"])
```
**Problem:** `settings` is never imported. The file imports `get_pool` from `api.database` and `ModerationService` from `api.services.moderation`, but has NO import for `settings`. Every authenticated API request crashes with `NameError: name 'settings' is not defined`.

**Fix:** Add this import at the top of the file:
```python
from api.config import settings
```
This is the Pydantic Settings instance that contains `jwt_secret` loaded from environment variables. Verify `api/config.py` exports a `settings` instance (it does — it's a module-level Pydantic `BaseSettings` singleton).

**Verification:** Trace the auth flow: `Authorization: Bearer <token>` → `AuthMiddleware.dispatch()` → line 39 must now resolve `settings.jwt_secret` without error.

---

### Bug N2: `api/routes/billing.py:46` — Wrong arguments to `create_checkout_session()`
**File:** `api/routes/billing.py`
**Line:** 46
**Current code:**
```python
result = await stripe_service.create_checkout_session(user_id, row["email"], body.plan, body.annual)
```
**Problem:** The method signature in `src/billing/stripe_service.py:28` is:
```python
async def create_checkout_session(self, db_pool, workos_user_id: str, email: str, plan: str, annual: bool = False) -> dict:
```
The first parameter after `self` is `db_pool`, but the caller passes `user_id` as the first argument. This means `db_pool` receives a string (the user ID), and the method crashes when it tries to call `db_pool.fetchrow()` on a string.

**Fix:** Change line 46 in `billing.py` to pass `pool` as the first argument:
```python
result = await stripe_service.create_checkout_session(pool, user_id, row["email"], body.plan, body.annual)
```
Note: `pool` is already defined on line 40: `pool = get_pool()`. Just reuse it.

---

### Bug N3: `api/routes/billing.py:86` — Wrong arguments to `create_portal_session()`
**File:** `api/routes/billing.py`
**Line:** 86
**Current code:**
```python
result = await stripe_service.create_portal_session(row["stripe_customer_id"])
```
**Problem:** The method in `stripe_service.py:94` is named `create_customer_portal` (NOT `create_portal_session`), and its signature is:
```python
async def create_customer_portal(self, db_pool, workos_user_id: str) -> dict:
```
Two issues: (1) wrong method name, (2) wrong arguments (needs `db_pool` and `workos_user_id`, not `stripe_customer_id`).

**Fix:** Change line 86 to:
```python
result = await stripe_service.create_customer_portal(pool, user_id)
```
Note: `pool` is already defined on line 80, and `user_id` on line 76. The `create_customer_portal` method internally fetches the `stripe_customer_id` from the database using the `workos_user_id`.

---

### Bug N4: `src/tui/panels/activity_feed.py` — ImportError from non-existent events
**File:** `src/tui/panels/activity_feed.py`
**Lines:** 10-19
**Current code:**
```python
from src.core.events import (
    AgentCompleted,
    AgentDispatched,
    AgentStatusUpdate,
    CostUpdated,           # DOES NOT EXIST
    OrchestratorNarration,
    PatchProposed,         # DOES NOT EXIST
    SecurityAlert,         # DOES NOT EXIST
    VerificationUpdate,    # DOES NOT EXIST
)
```
**Problem:** 4 of the 8 imported events do not exist in `src/core/events.py`. The actual events defined in events.py are:
- `CostUpdated` → does NOT exist (there is no CostUpdated event anywhere)
- `PatchProposed` → does NOT exist (there is `PatchSetProposed` and `PatchApplied` but no `PatchProposed`)
- `SecurityAlert` → does NOT exist
- `VerificationUpdate` → does NOT exist

This causes an `ImportError` at module load time, which means the **entire activity feed panel fails to load**.

**Fix:** You have two options:

**Option A (Recommended): Define the missing events in `src/core/events.py`:**
Add these 4 event classes to the end of `src/core/events.py`:
```python
class CostUpdated(Message):
    """Emitted when task cost is calculated."""
    def __init__(self, task_cost: float, daily_total: float, monthly_total: float = 0.0) -> None:
        super().__init__()
        self.task_cost = task_cost
        self.daily_total = daily_total
        self.monthly_total = monthly_total

class PatchProposed(Message):
    """Emitted when a single file patch is proposed by an agent."""
    def __init__(self, filepath: Path, diff_text: str, agent_id: str) -> None:
        super().__init__()
        self.filepath = filepath
        self.diff_text = diff_text
        self.agent_id = agent_id

class SecurityAlert(Message):
    """Emitted when security scanning finds an issue."""
    def __init__(self, severity: str, details: str, filepath: Path) -> None:
        super().__init__()
        self.severity = severity
        self.details = details
        self.filepath = filepath

class VerificationUpdate(Message):
    """Emitted during arbiter verification stages."""
    def __init__(self, step_name: str, passed: bool, detail: str = "") -> None:
        super().__init__()
        self.step_name = step_name
        self.passed = passed
        self.detail = detail
```

Make sure to add `from pathlib import Path` at the top of events.py if not already present (it IS already imported on line 4).

**Option B: Remove the unused handlers from activity_feed.py.** Remove the 4 dead imports AND their corresponding handler methods (`on_cost_updated`, `on_patch_proposed`, `on_security_alert`, `on_verification_update`). This is simpler but loses functionality.

**Go with Option A** — these events are referenced in CLAUDE.md's event contracts and should exist.

---

## GROUP B: P1 High Priority (Feature-breaking bugs)

### Bug N5: `src/core/parallel_dispatcher.py:329` — Only first tool call processed
**File:** `src/core/parallel_dispatcher.py`
**Lines:** 288-329
**Current code:**
```python
if chunk.tool_calls:
    for tc in chunk.tool_calls:
        # ... process ONE tool call ...
        messages.append({"role": "assistant", ...})
        messages.append({"role": "tool", ...})
        content_parts = []
        break  # ← BREAKS after first tool call
```
**Problem:** When an LLM returns multiple tool calls in one turn (e.g., `glob_files` + `read_file`), only the first tool call is executed. The `break` at line 329 exits the `for tc in chunk.tool_calls` loop after the first iteration.

**Fix:** Process ALL tool calls before appending to messages. Restructure the tool-call block:
```python
if chunk.tool_calls:
    # Process ALL tool calls in this chunk
    tool_results = []
    for tc in chunk.tool_calls:
        tool_name = tc.get("function", {}).get("name", "")
        tool_args = tc.get("function", {}).get("arguments", {})
        if isinstance(tool_args, str):
            import json
            try:
                tool_args = json.loads(tool_args)
            except json.JSONDecodeError:
                tool_args = {}

        await queue.put({
            "type": "agent_tool_call",
            "agent_id": slot.agent_id,
            "model_name": slot.model.name,
            "tool_name": tool_name,
            "args": tool_args,
        })
        slot.tool_calls_log.append({"tool": tool_name, "args": tool_args})

        try:
            result = execute_tool(tool_name, tool_args)
        except Exception as e:
            result = f"Tool error: {e}"

        tool_results.append({
            "role": "tool",
            "content": str(result),
            "tool_call_id": tc.get("id", ""),
            "name": tool_name,
        })

    # Append assistant message with ALL tool calls + ALL results
    assistant_content = "".join(content_parts)
    messages.append({
        "role": "assistant",
        "content": assistant_content or None,
        "tool_calls": chunk.tool_calls,
    })
    messages.extend(tool_results)
    content_parts = []
    break  # Break OUTER streaming loop to re-enter with tool results
```
The key change: the `break` now breaks the `async for chunk` streaming loop (not the `for tc` tool loop), and ALL tool results are appended.

---

### Bug N6: `src/core/chat_pipeline.py:135` — Tools and temperature not passed to agent
**File:** `src/core/chat_pipeline.py`
**Lines:** 123-135
**Current code:**
```python
payload = {
    "model": model_def.id,
    "messages": messages,
    "tools": get_tool_definitions(),
    "temperature": 0.2
}
# ...
async for chunk in agent.chat_stream(payload["messages"]):
```
**Problem:** The `payload` dict contains `tools` and `temperature`, but `agent.chat_stream()` is only called with `payload["messages"]`. The tool definitions and temperature are built but never forwarded to the LLM API call. This means in Standard mode, the LLM doesn't know tools exist and cannot generate tool calls.

**Fix:** The `BaseAgent.chat_stream()` takes `messages: list[dict]`, but the underlying LiteLLM client needs tools and temperature as separate parameters. You need to either:

1. Pass tools/temperature through the agent's config before calling chat_stream:
```python
agent.config.tools = get_tool_definitions()
agent.config.temperature = 0.2
if self.default_tier == QualityTier.SCOUT:
    agent.config.max_tokens = 1000
```
Do this BEFORE the `while True:` loop (after line 86 where the agent is created), and remove the payload dict entirely — just pass `messages` directly.

2. Or, if the agent's `chat_stream` implementation reads from `self.config.tools` when making the LiteLLM call, verify this by checking the LiteLLM client's `chat_stream` method. If it DOES read `self.config.tools`, then setting them on the config is the correct fix.

**Key:** Check `src/agents/litellm_client.py`'s `chat_stream()` method to see how it builds the LiteLLM `completion()` call. If it uses `self.config.tools`, set them. If it doesn't, you need to add tool forwarding to the agent base class.

---

### Bug N7: `src/tui/app.py:317` — Wrong parameter name for AgentDispatched
**File:** `src/tui/app.py`
**Line:** 317
**Current code:**
```python
self.post_message(AgentDispatched(agent_id=model_id, model_name=model_name))
```
**Problem:** `AgentDispatched.__init__` takes `agent_name` as the first parameter (see `src/core/events.py:151`):
```python
def __init__(self, agent_name: str, model_name: str, input_tokens: int = 0) -> None:
```
Using `agent_id=` raises `TypeError: __init__() got an unexpected keyword argument 'agent_id'`.

**Fix:**
```python
self.post_message(AgentDispatched(agent_name=model_name, model_name=model_name))
```

---

### Bug N8: `src/tui/app.py:803` — `event.annotation` doesn't exist
**File:** `src/tui/app.py`
**Lines:** 800-807
**Current code:**
```python
def on_annotation_action(self, event: AnnotationActionClicked) -> None:
    action = event.action
    annotation = event.annotation  # ← AttributeError!
    file_path = annotation.get("file_path", "") ...
```
**Problem:** `AnnotationActionClicked` has attributes `action`, `file_path`, `line_number`, `context` — NOT `annotation` (see `events.py:296-302`).

**Fix:** Replace lines 802-807 with direct event attribute access:
```python
def on_annotation_action(self, event: AnnotationActionClicked) -> None:
    action = event.action
    file_path = event.file_path
    line = event.line_number
    message = event.context.get("message", "")
    severity = event.context.get("severity", "info")
```

---

### Bug N9: `src/tui/panels/battle_view.py` — `Label(align="right")` crash
**File:** `src/tui/panels/battle_view.py`
**Problem:** Textual's `Label` widget does NOT accept an `align` keyword argument. This crashes on render.

**Fix:** Remove `align="right"` from all `Label()` constructors. Use CSS instead:
```css
.right-aligned { text-align: right; }
```
Then apply the class: `Label("text", classes="right-aligned")`

---

### Bug N10: `src/tools/sandbox.py:225` — `extract_symbols()` called with wrong arity
**File:** `src/tools/sandbox.py`
**Line:** 225
**Current code:**
```python
extract_symbols(full_path)
```
**Problem:** `extract_symbols` in `src/tools/tree_sitter_utils.py:62` requires TWO arguments:
```python
def extract_symbols(file_path: Path, content: str) -> FileSymbols:
```
Calling it with just `full_path` raises `TypeError: extract_symbols() missing 1 required positional argument: 'content'`.

**Fix:**
```python
content = full_path.read_text(errors="replace")
extract_symbols(full_path, content)
```

---

### Bug N11: `src/tools/lsp.py:349,382` — Content-Length uses char count instead of byte count
**File:** `src/tools/lsp.py`
**Lines:** 349, 382
**Current code:**
```python
content = f"Content-Length: {len(body)}\r\n\r\n{body}"
```
**Problem:** LSP protocol specifies `Content-Length` as byte count, but `len(body)` returns character count. For non-ASCII content (Unicode symbols, non-English code), the byte length differs from character length, causing protocol desync.

**Fix:** Use byte length:
```python
body_bytes = body.encode("utf-8")
header = f"Content-Length: {len(body_bytes)}\r\n\r\n"
proc.stdin.write(header.encode("utf-8") + body_bytes)
```
Apply this fix at BOTH locations (lines 349 and 382). Also update the corresponding `proc.stdin.write(content.encode())` to use the new pattern.

---

### Bug N12: `src/tui/widgets/toast.py` — `events.Click()` with no args
**File:** `src/tui/widgets/toast.py`
**Problem:** Textual's `Click` event requires a sender argument. Constructing `events.Click()` with no arguments crashes.

**Fix:** If the toast's click handler is simulating a click event, use `self.action_dismiss()` or a custom Message instead of fabricating a Click event. Check the toast code and replace the bare `events.Click()` with the appropriate Textual pattern.

---

### Bug N13: `src/core/config.py:159` — Falsiness check ignores `False`/`0` values
**File:** `src/core/config.py`
**Line:** 159
**Current code:**
```python
def get(self, key: str) -> Any:
    if has_proj and has_user:
        val = getattr(self._project_config, key)
        return val if val else getattr(self._user_config, key)
```
**Problem:** `if val` treats `False`, `0`, `""`, and `[]` as falsy. If the project config explicitly sets `auto_branch_for_changes = False` or `session_retention_days = 0`, this code falls through to the user config's default instead.

**Fix:** Use `is not None` check:
```python
return val if val is not None else getattr(self._user_config, key)
```
Also check lines 136 and 141 — the `_save_global`/`_save_project` methods filter with `if v is not None` which is correct (no change needed there). But the `get()` method on line 159 is the one with the bug.

---

### Bug N14: `api/middleware/rate_limit.py` — Rate limit runs before auth, `user_id` always None
**File:** `api/middleware/rate_limit.py`
**Lines:** 17-20
**Current code:**
```python
client_id = request.client.host
user_id = getattr(request.state, "user_id", None)
if user_id:
    client_id = user_id
```
**Problem:** In `api/main.py`, middleware is added in order. If `RateLimitMiddleware` is added BEFORE `AuthMiddleware`, `request.state.user_id` hasn't been set yet — so `user_id` is always `None` and rate limiting falls back to IP-based only.

**Fix:** In `api/main.py`, ensure `AuthMiddleware` is added BEFORE `RateLimitMiddleware`:
```python
app.add_middleware(AuthMiddleware)       # FIRST — sets request.state.user_id
app.add_middleware(RateLimitMiddleware)  # SECOND — can now read user_id
```
Note: Starlette middleware executes in REVERSE order of how they're added — the LAST added middleware runs FIRST. So the correct order is:
```python
app.add_middleware(RateLimitMiddleware)  # Added second, runs second
app.add_middleware(AuthMiddleware)       # Added last, runs first
```
Check `api/main.py` and verify the ordering. If `AuthMiddleware` is added first and `RateLimitMiddleware` second, SWAP them.

---

## GROUP C: P2 Medium Priority (Degraded functionality)

### Bug N15: `src/core/router.py:100` — String sorting of quality tiers
**File:** `src/core/router.py`
**Line:** 100
**Current code:**
```python
available.sort(key=lambda m: (m.quality_tiers[0] if m.quality_tiers else "", m.input_cost_per_mtok), reverse=True)
```
**Problem:** `quality_tiers` are strings like `"light"`, `"standard"`, `"max"`. String sorting with `reverse=True` produces: `standard > max > light` (alphabetical reverse), but the intended order is `max > standard > light`.

**Fix:** Use a numeric mapping:
```python
TIER_ORDER = {"max": 3, "standard": 2, "light": 1}
available.sort(
    key=lambda m: (TIER_ORDER.get(m.quality_tiers[0], 0) if m.quality_tiers else 0, m.input_cost_per_mtok),
    reverse=True,
)
```

---

### Bug N16: `src/core/project_context.py` — Unbounded `rglob("*")`
**File:** `src/core/project_context.py`
**Problem:** The file uses `rglob("*")` to scan the project directory without excluding `node_modules/`, `.git/`, `venv/`, etc. On large JavaScript projects, this hangs or uses excessive memory.

**Fix:** Add exclusion filtering. After the rglob, filter out common large directories:
```python
EXCLUDED_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache", "dist", "build", ".next"}

for path in project_root.rglob("*"):
    if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
        continue
    # ... process path
```
Or better yet, use `Workspace.get_instance().safe_walk()` which already respects `.gptcgtignore`.

---

### Bug N17: `src/tui/widgets/hunk_editor.py` — Enter key binding steals from TextArea
**File:** `src/tui/widgets/hunk_editor.py`
**Problem:** The widget binds `enter` to submit the hunk edit, but this intercepts the Enter key from the child `TextArea`, making it impossible to add newlines in multi-line edits.

**Fix:** Change the binding to `ctrl+enter` for submission:
```python
BINDINGS = [
    Binding("ctrl+enter", "submit_edit", "Apply Edit"),
    Binding("escape", "cancel_edit", "Cancel"),
]
```

---

### Bug N18: `api/middleware/rate_limit.py` — In-memory only rate limiter
**File:** `api/middleware/rate_limit.py`
**Problem:** The `self.cache` dict is per-process. With multiple Fly.io replicas, each instance has its own cache. A user can make 100 requests to replica A and 100 to replica B without hitting limits.

**Fix:** Replace with Redis-backed rate limiting using the existing `RedisConfig` from `ServiceRegistry`:
```python
import redis.asyncio as redis
from src.services.registry import services

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests=100, window_seconds=60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis = None
        self._fallback_cache = {}  # Local fallback if Redis unavailable

    async def _get_redis(self):
        if self._redis is None:
            try:
                self._redis = redis.from_url(services.redis.url)
            except Exception:
                return None
        return self._redis

    async def dispatch(self, request, call_next):
        client_id = getattr(request.state, "user_id", None) or request.client.host
        r = await self._get_redis()
        if r:
            key = f"ratelimit:{client_id}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, self.window_seconds)
            if count > self.max_requests:
                return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
        # ... fallback to local cache if Redis unavailable
        return await call_next(request)
```

---

### Bug N19: `proxy/main.py:23-26` — Module-level `services` access negates lazy loading
**File:** `proxy/main.py`
**Problem:** The file imports and accesses `services` at module level, which forces `ServiceRegistry` to initialize immediately — defeating the lazy `__getattr__` pattern from Phase 8's fix (Bug #4).

**Fix:** Move all `services` access inside function bodies (not module-level). For example, if there's a module-level `JWT_SECRET = services.jwt.secret`, move it inside the function that uses it:
```python
# BAD (module level):
JWT_SECRET = services.jwt.secret

# GOOD (inside function):
async def verify_proxy_auth(request):
    jwt_secret = services.jwt.secret  # Lazy access
    ...
```

---

### Bug N20: `src/billing/stripe_service.py` — Synchronous Stripe API calls block event loop
**File:** `src/billing/stripe_service.py`
**Lines:** 53, 88, 101, etc.
**Problem:** Methods like `create_checkout_session`, `create_credit_purchase_session`, `create_customer_portal` are `async` but call `stripe.checkout.Session.create()` and `stripe.billing_portal.Session.create()` which are synchronous blocking calls. This blocks the event loop during Stripe API round-trips.

**Fix:** Wrap synchronous Stripe calls in `asyncio.to_thread()`:
```python
import asyncio

# Instead of:
session = stripe.checkout.Session.create(**session_params)

# Use:
session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
```
Apply this to ALL synchronous `stripe.*` calls in the file (lines 53, 88, 101, 114).

---

### Bug N21: `proxy/database.py` — `close_db_pool()` doesn't null `_pool`
**File:** `proxy/database.py`
**Problem:** After closing the pool, `_pool` still references the closed pool object. Any subsequent call to `get_pool()` returns a closed, unusable pool instead of creating a new one.

**Fix:** Set `_pool = None` after closing:
```python
async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
```

---

### Bug N22: `api/routes/auth.py:18-19` — Dead dev variables
**File:** `api/routes/auth.py`
**Lines:** 18-19
**Problem:** `DEV_MODE` and `MOCK_CODE` variables are defined but no longer used (the dev bypass was removed in Phase 8). Dead code is an audit risk.

**Fix:** Delete lines 18-19 entirely.

---

### Bug N23: All agent files — Wrong tokenizer for non-OpenAI models
**Files:** `src/agents/anthropic.py`, `google.py`, `deepseek.py`, `xai.py`
**Problem:** All agents use OpenAI's `cl100k_base` tokenizer (via `tiktoken`) for `count_tokens()`, regardless of provider. This gives inaccurate token counts for Claude (uses its own tokenizer), DeepSeek, Gemini, etc.

**Fix:** This is a known limitation. For now, add a provider-specific multiplier as a heuristic:
```python
TOKEN_COUNT_MULTIPLIERS = {
    "anthropic": 1.1,    # Claude tokens are ~10% more than OpenAI's tokenizer estimates
    "google": 1.05,
    "deepseek": 1.0,     # Similar tokenizer
    "xai": 1.05,
}
```
Apply this in each agent's `count_tokens()` method. A precise fix would require provider-specific tokenizer libraries, which can be deferred to Phase 10.

---

## GROUP D: P3 Low Priority (Polish & Stubs)

### Bug N24: `src/tui/overlays/onboarding.py` — Step 5 preferences ignored
**File:** `src/tui/overlays/onboarding.py`
**Problem:** The onboarding flow's final step (preferences) collects user choices but doesn't persist them to `ConfigManager`. The selections are silently discarded.

**Fix:** In the step 5 completion handler, save selections to the config:
```python
config = self.app.config
config.set_user("default_quality_tier", selected_tier)
config.set_user("theme", selected_theme)
# etc.
```

---

### Bug N25: `src/tui/overlays/settings.py` — `mount()` during `compose()`
**File:** `src/tui/overlays/settings.py`
**Problem:** Calling `self.mount(widget)` inside `compose()` is a Textual anti-pattern. `compose()` should only `yield` widgets; dynamic mounting should happen in `on_mount()`.

**Fix:** Move any `self.mount()` calls from `compose()` to `on_mount()`.

---

### Bug N26: `src/core/mode_manager.py` — `check_credits()` always returns True
**File:** `src/core/mode_manager.py`
**Problem:** `check_credits()` is a stub that always returns `True`. There's no actual credit gating — users in any mode can proceed without credits.

**Fix:** Implement credit checking via the auth manager:
```python
def check_credits(self, mode: OperationMode) -> bool:
    cost = CREDIT_COSTS.get(mode, 5)
    try:
        from textual.app import App
        app = App.get_running_app()
        if hasattr(app, "status_bar"):
            return app.status_bar.credits_remaining >= cost
    except Exception:
        pass
    return True  # Allow if we can't check (BYOK mode)
```

---

### Bug N27: `src/core/context_compactor.py` — Over-budget handling is a no-op
**File:** `src/core/context_compactor.py`
**Problem:** The compactor's over-budget handler does nothing — it returns the messages unchanged. Context is never actually compacted.

**Fix:** Implement basic truncation strategy:
```python
def compact(self, messages: list[dict], budget_tokens: int) -> list[dict]:
    """Remove oldest non-system messages until within budget."""
    # Always keep system message (index 0) and last user message (index -1)
    if len(messages) <= 2:
        return messages

    system = messages[0] if messages[0]["role"] == "system" else None
    user_msg = messages[-1]
    middle = messages[1:-1] if system else messages[:-1]

    # Remove from oldest first
    while self._count_tokens(middle) + self._count_tokens([user_msg]) > budget_tokens and middle:
        middle.pop(0)

    result = []
    if system:
        result.append(system)
    result.extend(middle)
    result.append(user_msg)
    return result
```

---

### Bug N28: `src/core/memory.py` — Complete stub
**File:** `src/core/memory.py`
**Problem:** The memory system has no implementation. Conversation memory doesn't persist across sessions.

**Fix:** This is a larger feature. For Phase 9, add a minimal working implementation:
```python
class ProjectMemory:
    def __init__(self, workspace):
        self.memory_path = workspace.get_project_root() / ".gptcgt" / "memory.json"
        self._facts = self._load()

    def _load(self) -> list[dict]:
        if self.memory_path.exists():
            return json.loads(self.memory_path.read_text())
        return []

    def _save(self) -> None:
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_path.write_text(json.dumps(self._facts, indent=2))

    def add_fact(self, fact: str, source: str = "") -> None:
        self._facts.append({"fact": fact, "source": source, "timestamp": datetime.now().isoformat()})
        self._save()

    def get_context(self, max_facts: int = 20) -> str:
        recent = self._facts[-max_facts:]
        return "\n".join(f"- {f['fact']}" for f in recent)
```

---

### Bug N29: `src/billing/stripe_service.py:129-130` — Webhook idempotency dict cleared entirely
**File:** `src/billing/stripe_service.py`
**Lines:** 129-130
**Current code:**
```python
if len(_processed_webhook_events) > 1000:
    _processed_webhook_events.clear()
```
**Problem:** Clearing the entire set means all recent events become "unprocessed" again. If Stripe retries any of those webhooks, they'll be processed again (double credits, duplicate subscriptions).

**Fix:** Keep the most recent 500 events instead of clearing all:
```python
if len(_processed_webhook_events) > 1000:
    # Keep only the most recent events (convert to list, slice, convert back)
    # Since sets are unordered, this is imperfect — use an OrderedDict or deque instead
    from collections import deque
    # Better: replace the module-level set with a deque
    pass
```

Actually, the proper fix is to replace the `set` with a `collections.deque(maxlen=1000)`:
```python
from collections import deque
_processed_webhook_events: deque[str] = deque(maxlen=1000)
```
Then remove the manual size check entirely. The deque automatically discards the oldest events when it exceeds maxlen. The `in` check (`event_id in _processed_webhook_events`) works on deques.

---

### Bug N30: `src/auth/auth_manager.py` — Dev mode bypass still present
**File:** `src/auth/auth_manager.py`
**Problem:** The auth manager has a dev mode bypass that allows unauthenticated access. This should have been removed along with the middleware bypass in Phase 8.

**Fix:** Find and remove any `DEV_MODE`, `MOCK_TOKEN`, or `if dev_mode:` patterns. Ensure all auth paths require real tokens.

---

## Verification Checklist

After completing all fixes, verify:

1. **Auth middleware:** `python -c "from api.middleware.auth import AuthMiddleware"` → no ImportError
2. **Activity feed:** `python -c "from src.tui.panels.activity_feed import ActivityFeedPanel"` → no ImportError
3. **Events:** `python -c "from src.core.events import CostUpdated, PatchProposed, SecurityAlert, VerificationUpdate"` → no ImportError
4. **Billing routes:** Trace `create_checkout_session` call in billing.py → matches stripe_service.py signature
5. **Billing portal:** Trace `create_customer_portal` call → matches stripe_service.py signature
6. **App events:** `AgentDispatched(agent_name=...)` not `agent_id=`
7. **Sandbox:** `extract_symbols(path, content)` — two args
8. **Run tests:** `cd gptcgt && pytest tests/ -v`
9. **Lint:** `ruff check src/ api/ proxy/`

## Summary

| Group | Count | Files Affected | Risk if Unfixed |
|-------|-------|----------------|-----------------|
| **A: P0 Showstoppers** | 4 | auth.py, billing.py, activity_feed.py, events.py | API completely broken, TUI panel crashes |
| **B: P1 High** | 10 | parallel_dispatcher.py, chat_pipeline.py, app.py (x2), battle_view.py, sandbox.py, lsp.py, toast.py, config.py, rate_limit.py | Core features broken, crashes |
| **C: P2 Medium** | 9 | router.py, project_context.py, hunk_editor.py, rate_limit.py, proxy/main.py, stripe_service.py, database.py, auth.py, agents/* | Degraded performance, wrong behavior |
| **D: P3 Low** | 7 | onboarding.py, settings.py, mode_manager.py, context_compactor.py, memory.py, stripe_service.py, auth_manager.py | Polish, stubs, dead code |

**Priority order:** Fix Group A first (4 bugs), then Group B (10 bugs). Groups C and D can wait for Phase 10 if needed. Group A alone will take the API from "completely broken" to "functional."
