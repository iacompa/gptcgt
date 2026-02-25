export const metadata = { title: "Configuration — gptcgt Docs" };

export default function DocsConfig() {
    return (
        <>
            <h1>Configuration</h1>
            <p>gptcgt uses a cascade configuration system consisting of global user defaults and project-specific overrides.</p>

            <h2>Global Settings (<code>~/.gptcgt/global.toml</code>)</h2>
            <p>Global settings define your UI preferences and default operations across all projects.</p>
            <pre><code>{`# Appearance
theme = "midnight"

# Defaults
default_quality_tier = "standard"
default_operation_mode = "standard"

# Legal & Billing
tos_accepted = true
overage_enabled = false
auto_downgrade_on_limit = true
daily_spending_warning = 5.0
`}</code></pre>

            <h2>Project Settings (<code>.gptcgt/config.toml</code>)</h2>
            <p>Project settings live directly in your repository. They define context boundaries and workflow hooks unique to the codebase.</p>
            <pre><code>{`# Project identity
project_name = "my-nextjs-app"

# Context Management
always_include_in_context = ["types/global.d.ts", "lib/api.ts"]
never_include_in_context = ["public/images", "package-lock.json"]
custom_ignore_patterns = ["*.min.js", ".next/"]

# Git integration
auto_branch_for_changes = true
branch_prefix = "gptcgt/"
`}</code></pre>
        </>
    );
}
