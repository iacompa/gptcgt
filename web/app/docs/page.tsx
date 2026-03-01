import Link from "next/link";

export const metadata = { title: "Documentation — gptcgt" };

export default function DocsOverview() {
    return (
        <>
            <h1>gptcgt Documentation</h1>
            <p>
                Welcome to the official documentation for <strong>gptcgt</strong> — the multi-model AI coding terminal
                that transforms your shell into an intelligent IDE. gptcgt connects to the world&apos;s most capable
                Large Language Models and lets them read, reason about, and edit your codebase directly.
            </p>

            <div className="not-prose grid grid-cols-1 sm:grid-cols-2 gap-3 my-6">
                {[
                    { href: "/docs/getting-started", title: "🚀 Getting Started", desc: "Install and launch in under 2 minutes" },
                    { href: "/docs/modes", title: "⚡ Operation Modes", desc: "Scout, Standard, Ensemble, Architect, Battle" },
                    { href: "/docs/autonomous", title: "🤖 Autonomous Mode", desc: "Let agents build entire features hands-free" },
                    { href: "/docs/commands", title: "⌨️ Commands & Shortcuts", desc: "Full keyboard reference and slash commands" },
                    { href: "/docs/keys", title: "🔑 API Keys & Auth", desc: "BYOK or Managed Credits — your choice" },
                    { href: "/docs/config", title: "⚙️ Configuration", desc: "Global and per-project settings" },
                    { href: "/docs/costs", title: "💰 Costs & Billing", desc: "Transparent pricing with 5 safety layers" },
                    { href: "/docs/elo-arena", title: "🏆 ELO Arena", desc: "Models compete. The best get picked more." },
                    { href: "/docs/security", title: "🛡️ Security & Safety", desc: "Sandboxing, scanning, and crash recovery" },
                    { href: "/docs/custom-models", title: "🧩 Custom Models", desc: "Bring your own Ollama, vLLM, or OpenRouter models" },
                    { href: "/docs/faq", title: "❓ FAQ", desc: "Common questions answered" },
                ].map((card) => (
                    <Link key={card.href} href={card.href} className="block p-4 rounded-lg border border-gray-800 bg-gray-900/50 hover:border-indigo-500/50 hover:bg-gray-800/50 transition-all group">
                        <p className="text-white font-semibold text-sm group-hover:text-indigo-400 transition-colors">{card.title}</p>
                        <p className="text-gray-500 text-xs mt-1">{card.desc}</p>
                    </Link>
                ))}
            </div>

            <h2>What Makes gptcgt Different</h2>
            <ul>
                <li><strong>Multi-model orchestration</strong> — Run 3+ AI models on the same task and pick the best result, verified by an impartial Arbiter.</li>
                <li><strong>Terminal-native</strong> — No Electron app. gptcgt lives in your shell, right next to your build tools, Git, and CI/CD pipelines.</li>
                <li><strong>Provider-agnostic</strong> — OpenAI, Anthropic, Google, DeepSeek, xAI, Mistral, Groq, Cohere, OpenRouter, or your own local models.</li>
                <li><strong>Transparent cost tracking</strong> — See exactly what every token costs, with 5 independent safety layers to prevent runaway spend.</li>
                <li><strong>Autonomous execution</strong> — Give it a goal, walk away, and come back to a fully implemented feature with test coverage.</li>
                <li><strong>Security-first</strong> — Workspace sandboxing prevents the AI from touching files outside your project. All generated code is scanned for vulnerabilities.</li>
                <li><strong>ELO-ranked routing</strong> — Models compete head-to-head. Winners get selected more often over time.</li>
            </ul>

            <h2>Supported Languages</h2>
            <p>gptcgt works with any language or framework. It uses <strong>tree-sitter</strong> for fast AST parsing and an optional <strong>Language Server Protocol (LSP)</strong> client for cross-file reference checking. Pre-configured support for:</p>
            <ul>
                <li>Python (pyright / pylsp)</li>
                <li>TypeScript / JavaScript (ts-language-server)</li>
                <li>Rust (rust-analyzer)</li>
                <li>Go (gopls)</li>
                <li>Java (jdtls)</li>
                <li>C / C++ (clangd)</li>
            </ul>
            <p>If an LSP isn&apos;t installed for your language, gptcgt still works — you just skip the cross-file reference verification step.</p>
        </>
    );
}
