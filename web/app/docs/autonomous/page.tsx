export const metadata = { title: "Autonomous Mode — gptcgt Docs" };

export default function DocsAutonomous() {
    return (
        <>
            <h1>Autonomous Mode</h1>
            <p>Autonomous mode lets you give gptcgt a high-level goal — like &ldquo;Build a REST API for user management&rdquo; — and walk away. The system plans, implements, tests, and iterates without human intervention, pausing only when it needs your input or reaches a safety boundary.</p>

            <h2>How It Works</h2>
            <ol>
                <li><strong>Plan Generation</strong> — The orchestrator drafts a project plan with numbered subtasks, stored in <code>.gptcgt/phase.md</code></li>
                <li><strong>Subtask Execution Loop</strong> — Each subtask flows through the full DAG pipeline: intent analysis → context gathering → model routing → code generation → testing → arbiter verification</li>
                <li><strong>Self-Healing</strong> — If a test fails, the TesterAgent regenerates the code (up to 3 attempts) using the failure output as feedback</li>
                <li><strong>Phase Tracking</strong> — Progress updates <code>.gptcgt/phase.md</code> in real-time so the AI always knows where it is</li>
                <li><strong>Completion Summary</strong> — When all subtasks finish, you get a summary of what was done, what failed, and what it cost</li>
            </ol>

            <h2>Safety Boundaries</h2>
            <p>Autonomous mode has <strong>4 independent safety checks</strong> that prevent runaway execution:</p>

            <h3>1. Budget Guard</h3>
            <p>Before every subtask, the system checks total spend against your configured limits. If spent exceeds the budget, execution pauses immediately.</p>
            <pre><code>{`# In ~/.gptcgt/global.toml
max_spend_per_task = 2.0    # $2 max per individual task
daily_spend_limit = 10.0    # $10/day hard stop (BYOK mode)`}</code></pre>

            <h3>2. Iteration Cap</h3>
            <p>A hard ceiling on how many subtasks the autonomous loop will execute before pausing for your review.</p>
            <pre><code>{`# In ~/.gptcgt/global.toml
max_autonomous_iterations = 50`}</code></pre>

            <h3>3. Token Cap</h3>
            <p>Each individual task is capped at 500,000 tokens by default. This prevents accidental context window explosions when processing large files.</p>
            <pre><code>{`max_tokens_per_task = 500000`}</code></pre>

            <h3>4. User Cancellation</h3>
            <p>Press <code>Ctrl+C</code> or <code>Escape</code> at any time. The system cancels the current subtask gracefully and preserves all work done so far.</p>

            <h2>Agent Communication</h2>
            <p>In autonomous mode, multiple agents collaborate via a <strong>PubSub message bus</strong>:</p>
            <ul>
                <li><strong>Orchestrator</strong> — Plans and coordinates the overall workflow</li>
                <li><strong>Coder Agent</strong> — Generates code changes as unified diffs</li>
                <li><strong>Tester Agent</strong> — Generates and runs tests in an isolated sandbox</li>
                <li><strong>Arbiter</strong> — Scores and validates each change before approval</li>
            </ul>
            <p>Agents communicate through structured <code>AgentMessage</code> objects with type, sender, recipient, and payload. Messages are logged in the bottom-left log panel so you can see exactly what each agent is doing.</p>

            <h2>Agent Memory</h2>
            <p>The system maintains memory across sessions:</p>
            <ul>
                <li><strong><code>.gptcgt/phase.md</code></strong> — Project file map with line counts, modification dates, and development phases</li>
                <li><strong><code>.gptcgt/project.md</code></strong> — Auto-detected tech stack summary (language, framework, test runner, linter)</li>
                <li><strong><code>.gptcgt/memory.json</code></strong> — Telemetry entries recording which models were used, costs, and success rates</li>
                <li><strong><code>.gptcgt/agents/tester.md</code></strong> — The TesterAgent&apos;s memory file of failure patterns it has learned from</li>
            </ul>
            <p>This memory prevents the agents from repeating the same mistakes and helps them understand the project&apos;s structure without needing to re-analyze every time.</p>

            <h2>Crash Recovery</h2>
            <p>If gptcgt crashes mid-autonomous-run, your work isn&apos;t lost:</p>
            <ul>
                <li>A PID-locked <code>running.lock</code> file detects the crash on next startup</li>
                <li>State is auto-saved atomically to <code>.gptcgt/recovery/state.json</code></li>
                <li>Unapplied diffs are backed up to <code>.gptcgt/recovery/diffs/</code></li>
                <li>On restart, gptcgt offers to resume from where it left off</li>
            </ul>

            <h2>Best Practices</h2>
            <ul>
                <li><strong>Always commit before starting</strong> — Run <code>git commit</code> so you have a clean rollback point</li>
                <li><strong>Be specific with your goal</strong> — &ldquo;Build a user registration system with email verification and password reset&rdquo; works better than &ldquo;build auth&rdquo;</li>
                <li><strong>Start with smaller iteration caps</strong> while you learn the system&apos;s behavior</li>
                <li><strong>Review the phase.md</strong> after an autonomous run to understand what was done</li>
            </ul>
        </>
    );
}
