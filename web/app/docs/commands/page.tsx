export const metadata = { title: "Commands & Shortcuts — gptcgt Docs" };

export default function DocsCommands() {
    return (
        <>
            <h1>Commands &amp; Shortcuts</h1>
            <p>gptcgt is designed for absolute keyboard efficiency. You can control the entire environment without touching your mouse.</p>

            <h2>Core Slash Commands</h2>
            <ul>
                <li><code>/help</code> — Show the help overlay</li>
                <li><code>/setup</code> — Re-run the onboarding wizard</li>
                <li><code>/clear</code> — Clear the current chat display</li>
                <li><code>/status</code> — Check AI provider health and latency</li>
                <li><code>/version</code> — Show application version</li>
            </ul>

            <h2>Account &amp; Billing Commands</h2>
            <ul>
                <li><code>/login</code> — Start WorkOS device flow authentication</li>
                <li><code>/logout</code> — Sign out of your account</li>
                <li><code>/credits</code> — Check your remaining managed credits</li>
                <li><code>/billing</code> — Open the web dashboard to manage subscriptions</li>
            </ul>

            <h2>Global Keyboard Shortcuts</h2>
            <ul>
                <li><strong>Ctrl+P</strong> — Search workspace files (Command Palette)</li>
                <li><strong>Ctrl+B</strong> — Toggle left File Tree panel</li>
                <li><strong>Ctrl+J</strong> — Toggle right Chat panel</li>
                <li><strong>Ctrl+Q</strong> — Open Quality Tier selector</li>
                <li><strong>Ctrl+T</strong> — Cycle through color themes</li>
                <li><strong>Ctrl+,</strong> — Open application settings</li>
                <li><strong>Tab</strong> — Cycle focus between active panels</li>
            </ul>
        </>
    );
}
