export const metadata = { title: "Costs & Billing — gptcgt Docs" };

export default function DocsCosts() {
    return (
        <>
            <h1>Costs & Billing</h1>
            <p>gptcgt is engineered for absolute financial transparency.</p>

            <h2>The Cost Breakdown</h2>
            <p>At the bottom of the right-hand chat panel, you will notice a live cost summary. Every time a task completes, whether using your API keys or Managed Credits, the orchestrator computes the exact input token and output token count against the current provider pricing.</p>

            <h2>Managed Credit Conversion</h2>
            <p>If you are signed in, costs are mapped to our internal credit system. Roughly, 1 Credit = $0.01 worth of blended compute.</p>

            <h2>Spending Caps</h2>
            <p>You can enforce strict spending limits within the TUI or on the Web Dashboard.</p>
            <ul>
                <li><strong>Overage Protection</strong>: If disabled, operations automatically halt via a 402 exception when your monthly subscription runs out.</li>
                <li><strong>Daily Warning</strong>: Triggers a toast notification if your session cost exceeds a predefined limit (default: $5.00).</li>
                <li><strong>Hard Caps</strong>: A strict integer limit on your account that blocks all further API proxy routing for the billing cycle.</li>
            </ul>
        </>
    );
}
