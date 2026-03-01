export const metadata = { title: "Configuration — gptcgt Docs" };

export default function DocsConfig() {
    return (
        <>
            <h1>Configuration</h1>
            <p>gptcgt uses a <strong>cascading configuration system</strong>: global user defaults + project-specific overrides. Project settings take priority where both define the same key.</p>

            <h2>Global Settings</h2>
            <p>Stored at <code>~/.gptcgt/global.toml</code>. These apply across all projects.</p>
            <pre><code>{`# ── Appearance ──
theme = "midnight"                    # Color theme

# ── Defaults ──
default_quality_tier = "standard"     # scout | standard | ensemble | architect
default_operation_mode = "standard"   # Default mode when launching

# ── Model Overrides ──
# Pin specific models to specific agent roles:
coder_model = ""           # e.g. "anthropic/claude-3.5-sonnet"
orchestrator_model = ""    # The model that analyzes tasks
arbiter_model = ""         # The model that judges Ensemble results
architect_model = ""       # The model that generates plans
scout_model = ""           # The model for Scout mode
tester_model = ""          # The model that generates tests

# ── Billing & Safety ──
overage_enabled = false               # Allow pay-as-you-go when credits run out
auto_downgrade_on_limit = true        # Suggest Scout when credits are low
daily_spend_limit = 10.0              # BYOK daily hard stop ($)
max_spend_per_task = 2.0              # Max $ per individual task
max_tokens_per_task = 500000          # Token cap per task

# ── Autonomous Mode ──
max_autonomous_iterations = 50        # Max subtasks before pausing
allow_auto_tiering = true             # Let agents pick their own model tier

# ── Privacy ──
telemetry_enabled = false             # Send anonymous usage analytics
store_chat_on_disk = true             # Persist chat history to disk
session_retention_days = 90           # How long to keep old sessions

# ── Behavior ──
confirm_before_apply = true           # Show diff approval before applying
auto_security_scan = true             # Scan every change for vulnerabilities
show_cost_after_task = true           # Display cost breakdown after tasks
show_tier_comparison = true           # Show what other tiers would have done`}</code></pre>

            <h2>Project Settings</h2>
            <p>Stored at <code>.gptcgt/config.toml</code> in your project root. These override global settings and can be committed to Git for team-wide consistency.</p>
            <pre><code>{`# ── Project Identity ──
project_name = "my-nextjs-app"
project_description = "E-commerce platform"

# ── Languages & Tools ──
primary_language = "typescript"
test_command = "npm test"              # Auto-detected if not set
lint_command = "eslint ."              # Auto-detected if not set
build_command = "npm run build"

# ── Context Management ──
# Files always included in AI context (important types, configs):
always_include_in_context = [
  "types/global.d.ts",
  "lib/api.ts",
  "prisma/schema.prisma"
]

# Files never sent to the AI (large, binary, irrelevant):
never_include_in_context = [
  "public/images",
  "package-lock.json",
  "*.min.js"
]

# Additional ignore patterns beyond defaults:
custom_ignore_patterns = [".next/", "coverage/"]

# ── Agent Preferences ──
preferred_orchestrator_model = ""      # Override the router for this project
preferred_coding_model = ""

# ── Git Integration ──
auto_branch_for_changes = true         # Create a branch before applying changes
branch_prefix = "gptcgt/"             # Branch names: gptcgt/fix-auth-bug`}</code></pre>

            <h2>Auto-Detection</h2>
            <p>On first launch in a new project, gptcgt auto-detects:</p>
            <ul>
                <li><strong>Language</strong> — By counting file extensions (Python, JavaScript, TypeScript, Go, Rust)</li>
                <li><strong>Test command</strong> — Detects pytest, npm test from pyproject.toml or package.json</li>
                <li><strong>Linter</strong> — Detects Ruff, ESLint from config files</li>
            </ul>
            <p>You can override any auto-detected value by setting it explicitly in the config.</p>

            <h2>Ignore Patterns</h2>
            <p>Create a <code>.gptcgtignore</code> file in your project root (same syntax as <code>.gitignore</code>) to exclude files from the AI&apos;s view. By default, these directories are always ignored:</p>
            <pre><code>{`node_modules/  .git/  __pycache__/  venv/  .venv/
dist/  build/  .eggs/  *.egg-info/  .tox/
.mypy_cache/  .ruff_cache/  .pytest_cache/`}</code></pre>

            <h2>Config Precedence</h2>
            <ol>
                <li><strong>Project config</strong> (<code>.gptcgt/config.toml</code>) — Highest priority</li>
                <li><strong>Global config</strong> (<code>~/.gptcgt/global.toml</code>) — Fallback</li>
                <li><strong>Built-in defaults</strong> — Used if neither config specifies a value</li>
            </ol>
        </>
    );
}
