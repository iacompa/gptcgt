export const metadata = { title: "Getting Started — gptcgt Docs" };

export default function DocsGettingStarted() {
    return (
        <>
            <h1>Getting Started</h1>
            <p>Get up and running with gptcgt in under 2 minutes.</p>

            <h2>System Requirements</h2>
            <ul>
                <li><strong>Python 3.11+</strong> — Required for the core application</li>
                <li><strong>macOS, Linux, or WSL</strong> — Full terminal support (Windows native coming soon)</li>
                <li><strong>At least one AI provider API key</strong> — Or sign up for Managed Credits</li>
            </ul>

            <h2>Installation</h2>
            <p>We recommend <code>pipx</code> for a clean, isolated install:</p>
            <pre><code>{`# Recommended
pipx install gptcgt

# Alternative: standard pip
pip install gptcgt`}</code></pre>

            <h2>Launch</h2>
            <p>Navigate to any project directory and start gptcgt:</p>
            <pre><code>{`cd ~/my-project
gptcgt`}</code></pre>
            <p>gptcgt will automatically detect your project&apos;s language, test framework, and linter. It creates a <code>.gptcgt/</code> directory inside your project for configuration, phase tracking, and agent memory.</p>

            <h2>First-Run Onboarding</h2>
            <p>The first time you launch gptcgt, the <strong>onboarding wizard</strong> walks you through:</p>
            <ol>
                <li><strong>Authentication</strong> — Choose between BYOK (Bring Your Own Keys) or Managed Credits</li>
                <li><strong>API Key Entry</strong> — If BYOK, enter keys for the providers you want (OpenAI, Anthropic, Google, etc.)</li>
                <li><strong>Quality Tier</strong> — Set your default tier (Standard is recommended to start)</li>
                <li><strong>Theme Selection</strong> — Pick a color theme for the terminal UI</li>
                <li><strong>Terms of Service</strong> — Accept the ToS to proceed</li>
            </ol>
            <p>You can re-run the wizard at any time with <code>/setup</code>.</p>

            <h2>The Interface</h2>
            <p>gptcgt presents a three-panel terminal layout:</p>
            <ul>
                <li><strong>Left Panel — File Tree</strong>: Your project files with real-time change indicators</li>
                <li><strong>Center Panel — Code Viewer</strong>: View and inspect files with syntax highlighting</li>
                <li><strong>Right Panel — Chat</strong>: Talk to the AI, view diffs, and approve changes</li>
            </ul>
            <p>Toggle panels with <code>Ctrl+B</code> (files), <code>Ctrl+J</code> (chat). Press <code>Tab</code> to cycle focus between panels.</p>

            <h2>Your First Task</h2>
            <p>Focus the chat input (<code>Tab</code> or <code>Ctrl+J</code>) and type a natural language request:</p>
            <pre><code>{`Add input validation to the signup form in auth.py`}</code></pre>
            <p>gptcgt will:</p>
            <ol>
                <li><strong>Analyze intent</strong> — Determine this is an &ldquo;edit&rdquo; task with complexity ~4/10</li>
                <li><strong>Route to the best model</strong> — Based on complexity, your tier, and ELO ratings</li>
                <li><strong>Gather context</strong> — Find relevant files using AST maps and symbol references</li>
                <li><strong>Generate changes</strong> — Stream the response with a unified diff</li>
                <li><strong>Present for approval</strong> — You review the diff and accept or reject it</li>
                <li><strong>Security scan</strong> — Every change is scanned for vulnerabilities before application</li>
            </ol>

            <h2>What Happens Behind the Scenes</h2>
            <p>When you submit a task, it flows through a <strong>DAG (Directed Acyclic Graph) pipeline</strong>:</p>
            <pre><code>{`InitAnalyze → GatherContext → RouteTask → PrepareBlackboard
    ↓
[ArchitectPlan] or [StandardExecution] or [ParallelExecution]
    ↓
Arbiter Verification → Security Scan → Present to User`}</code></pre>
            <p>Each node in the pipeline is traceable — you can see timing data and transitions in the log panel.</p>

            <h2>Next Steps</h2>
            <ul>
                <li>Learn about <a href="/docs/modes">Operation Modes</a> to choose the right power level</li>
                <li>Set up <a href="/docs/autonomous">Autonomous Mode</a> for hands-free feature building</li>
                <li>Explore <a href="/docs/commands">Commands &amp; Shortcuts</a> for keyboard efficiency</li>
            </ul>
        </>
    );
}
