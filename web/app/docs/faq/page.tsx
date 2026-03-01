import Link from "next/link";

export const metadata = { title: "FAQ — gptcgt Docs" };

export default function DocsFAQ() {
    return (
        <>
            <h1>Frequently Asked Questions</h1>

            <h2>General</h2>

            <h3>What is gptcgt?</h3>
            <p>gptcgt is a terminal-based AI coding IDE that connects to multiple Large Language Models (OpenAI, Anthropic, Google, DeepSeek, xAI, and more). It lets you chat with AI about your code, generate changes as diffs, run multiple models simultaneously, and even run fully autonomous coding sessions.</p>

            <h3>Is gptcgt free?</h3>
            <p>Yes — gptcgt is free to use with your own API keys (BYOK mode). You only pay the providers directly. Alternatively, you can subscribe to gptcgt Pro for Managed Credits, which simplifies billing and gives you access to all providers through a single account.</p>

            <h3>What languages does it support?</h3>
            <p>gptcgt works with <strong>any programming language</strong>. It uses tree-sitter for fast AST parsing and has pre-configured LSP support for Python, TypeScript/JavaScript, Rust, Go, Java, and C/C++. Other languages work fine — you just skip the cross-file reference verification.</p>

            <h2>Privacy &amp; Security</h2>

            <h3>Is my code sent to servers to train AI?</h3>
            <p>No. We use provider API endpoints with <strong>zero-data-retention agreements</strong>. We do not use user data, prompts, or code to train models. In BYOK mode, your code goes directly to the provider — we never see it. See the <Link href="/legal/privacy">Privacy Policy</Link>.</p>

            <h3>Where are my API keys stored?</h3>
            <p>Keys are stored in your operating system&apos;s native keychain (macOS Keychain, Windows Credential Locker, Linux Secret Service). They never touch disk in plaintext. The <code>keyring</code> Python library handles encryption.</p>

            <h3>Can the AI access files outside my project?</h3>
            <p>No. The Workspace security boundary resolves all file paths (including symlinks and <code>../</code> traversals) and rejects any access outside your project root. This is enforced at the deepest level — every file read, write, list, and delete operation goes through this gatekeeper.</p>

            <h3>What if the AI generates vulnerable code?</h3>
            <p>Every code change is automatically scanned by a 3-layer security system: custom regex patterns (instant), Semgrep (OWASP Top 10), and language-specific scanners (Bandit for Python). Critical vulnerabilities trigger an auto-fix attempt before presenting changes to you. See <Link href="/docs/security">Security &amp; Safety</Link>.</p>

            <h2>Usage</h2>

            <h3>What happens if the AI deletes my files?</h3>
            <p>We strongly recommend using Git. The AI does have access to file deletion tools if instructed. Always commit before starting high-impact operations (Architect, Ensemble, Autonomous). Crash recovery automatically backs up unapplied diffs in <code>.gptcgt/recovery/</code>.</p>

            <h3>How does Ensemble mode pick the winner?</h3>
            <p>An impartial Arbiter model reads all 3 solutions and scores them on correctness, completeness, code quality, and security. It selects the winner with evidence-backed reasoning. The losing models&apos; ELO ratings drop, and the winner&apos;s rises — so better models get selected more often over time.</p>

            <h3>Can I use gptcgt in a team?</h3>
            <p>Yes. Commit <code>.gptcgt/config.toml</code> to Git for shared project settings (context files, test commands, lint commands). Each team member uses their own API keys or managed account. The web dashboard supports team management for organizations.</p>

            <h3>What is the .gptcgt directory?</h3>
            <p>It stores project-specific state:</p>
            <ul>
                <li><code>config.toml</code> — Per-project configuration</li>
                <li><code>phase.md</code> — Project file map and development phases (auto-generated)</li>
                <li><code>project.md</code> — Auto-detected tech stack summary</li>
                <li><code>memory.json</code> — Agent telemetry and routing history</li>
                <li><code>recovery/</code> — Crash recovery state and diff backups</li>
            </ul>
            <p>Add <code>.gptcgt/</code> to <code>.gitignore</code> if you don&apos;t want to share state across the team (config.toml being the exception).</p>

            <h2>Billing</h2>

            <h3>How do I cancel my subscription?</h3>
            <p>Type <code>/billing</code> in the terminal or visit the Accounts page on the web dashboard. Cancellation takes effect at the end of the current billing cycle.</p>

            <h3>What happens when I run out of credits?</h3>
            <p>Depends on your settings:</p>
            <ul>
                <li><strong>Overage disabled</strong> (default) — Operations halt with a 402 error. The system suggests a cheaper mode.</li>
                <li><strong>Overage enabled</strong> — You continue with pay-as-you-go billing.</li>
                <li><strong>Auto-downgrade enabled</strong> — The system automatically suggests Scout mode instead of blocking.</li>
            </ul>

            <h3>Why not just use Cursor / Windsurf / another AI editor?</h3>
            <p>Those are excellent products, but they lock you into a VSCode fork. gptcgt brings AI orchestration natively into your terminal — right next to your build tools, Git, and servers. Key differentiators:</p>
            <ul>
                <li><strong>Multi-model</strong> — Run 3+ models simultaneously and pick the best result</li>
                <li><strong>ELO rankings</strong> — Models compete and improve over time</li>
                <li><strong>Transparent costs</strong> — See exactly what every token costs</li>
                <li><strong>Provider-agnostic</strong> — Not locked to one AI vendor</li>
                <li><strong>Terminal-native</strong> — No GUI overhead, works over SSH</li>
            </ul>
        </>
    );
}
