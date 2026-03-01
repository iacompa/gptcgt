export const metadata = { title: "Costs & Billing — gptcgt Docs" };

export default function DocsCosts() {
    return (
        <>
            <h1>Costs &amp; Billing</h1>
            <p>gptcgt is engineered for <strong>absolute financial transparency</strong>. You always know exactly what you&apos;re spending, and there are 5 independent safety layers to prevent accidental overspend.</p>

            <h2>Live Cost Tracking</h2>
            <p>At the bottom of the chat panel, a live cost summary updates after every task. The orchestrator computes exact input/output token counts against current provider pricing. You see:</p>
            <ul>
                <li>Model used and provider</li>
                <li>Input tokens and output tokens</li>
                <li>Exact cost in USD</li>
                <li>Running session total</li>
            </ul>

            <h2>Dynamic Price Syncing</h2>
            <p>On startup, gptcgt fetches the latest model pricing from LiteLLM&apos;s pricing database (with a 1.5-second timeout). This means your cost calculations always reflect current provider rates, not stale data from the last release.</p>

            <h2>The 5 Safety Layers</h2>
            <p>Every one of these layers works independently. Even if one fails, the others catch it.</p>

            <h3>Layer 1 — Per-Task Limits (Config)</h3>
            <p>Hard limits on any individual task:</p>
            <pre><code>{`# ~/.gptcgt/global.toml
max_spend_per_task = 2.0      # $2 max per individual task
max_tokens_per_task = 500000  # 500K token cap
daily_spend_limit = 10.0      # $10/day hard stop (BYOK)`}</code></pre>

            <h3>Layer 2 — Autonomous Loop Budget Guard</h3>
            <p>In autonomous mode, the total spend is checked before every subtask. If the cumulative cost exceeds the budget, execution pauses and notifies you.</p>

            <h3>Layer 3 — Credit Check (Managed)</h3>
            <p>Before every task using Managed Credits, the system performs an atomic credit check:</p>
            <ul>
                <li>Checks if you have enough credits for the selected mode</li>
                <li>If not, suggests a cheaper mode you can afford</li>
                <li>Uses <code>SELECT ... FOR UPDATE</code> row locking to prevent race conditions</li>
            </ul>

            <h3>Layer 4 — Spending Caps (Managed)</h3>
            <p>Server-side enforcement with graduated warnings:</p>
            <ul>
                <li><strong>80% used</strong> — Yellow warning indicator</li>
                <li><strong>95% used</strong> — Orange critical indicator</li>
                <li><strong>100% used</strong> — Red: all API requests blocked</li>
            </ul>
            <p>Email warnings are sent (max once per 24 hours) when your cap is hit.</p>

            <h3>Layer 5 — Smart Model Routing</h3>
            <p>The router automatically selects cheaper models for simple tasks. If you ask a quick question (complexity 1-3), it routes to a fast, cheap model instead of burning tokens on GPT-4 or Claude Opus.</p>

            <h2>Credit System (Managed Mode)</h2>
            <p>If using a gptcgt subscription, costs are abstracted into credits. Roughly, <strong>1 Credit ≈ $0.01</strong> of blended compute.</p>
            <ul>
                <li><strong>Monthly allowance</strong> — Credits reset each billing cycle</li>
                <li><strong>Overage protection</strong> — Configurable: either halt at 0 or allow pay-as-you-go overage</li>
                <li><strong>Auto-downgrade</strong> — If enabled, the system suggests Scout mode instead of blocking when credits run low</li>
                <li><strong>PAYG top-ups</strong> — Purchase additional credits that never expire</li>
            </ul>

            <h2>BYOK Cost Tracking</h2>
            <p>With your own API keys, gptcgt tracks costs locally but doesn&apos;t manage billing. You control spend through the config-level limits (Layer 1) and monitor via the live cost display. Routing telemetry is stored in <code>.gptcgt/memory.json</code>.</p>
        </>
    );
}
