export const metadata = { title: "Operation Modes — gptcgt Docs" };

export default function DocsModes() {
    return (
        <>
            <h1>Operation Modes</h1>
            <p>gptcgt separates AI behavior into <strong>6 distinct operation modes</strong>. Each mode controls how many models are dispatched, how verification works, and what it costs. Switch modes mid-session to match the task at hand.</p>

            <h2>Quick Comparison</h2>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead>
                        <tr className="border-b border-gray-800 text-left text-gray-400">
                            <th className="py-2 pr-4">Mode</th>
                            <th className="py-2 pr-4">Credits</th>
                            <th className="py-2 pr-4">Models</th>
                            <th className="py-2 pr-4">Best For</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-medium text-white">Scout</td><td className="py-2 pr-4">1</td><td className="py-2 pr-4">1 (lightweight)</td><td className="py-2 pr-4">Exploring, reading, Q&amp;A</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-medium text-white">Standard</td><td className="py-2 pr-4">5</td><td className="py-2 pr-4">1 (capable)</td><td className="py-2 pr-4">Daily coding tasks</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-medium text-white">Ensemble</td><td className="py-2 pr-4">25</td><td className="py-2 pr-4">3 parallel</td><td className="py-2 pr-4">Important changes, hard bugs</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-medium text-white">Architect</td><td className="py-2 pr-4">100</td><td className="py-2 pr-4">Multi-phase</td><td className="py-2 pr-4">Large features, refactors</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-medium text-white">Battle</td><td className="py-2 pr-4">25</td><td className="py-2 pr-4">2 head-to-head</td><td className="py-2 pr-4">Algorithm comparisons</td></tr>
                        <tr><td className="py-2 pr-4 font-medium text-white">Single Provider</td><td className="py-2 pr-4">5</td><td className="py-2 pr-4">1 (locked vendor)</td><td className="py-2 pr-4">Vendor-specific needs</td></tr>
                    </tbody>
                </table>
            </div>

            <h2>🔭 Scout Mode</h2>
            <p><strong>Cost: 1 Credit</strong> — The cheapest option. Scout uses a fast, lightweight model to navigate your codebase without making edits. It reads directory structures, builds AST maps via tree-sitter, and answers questions like &ldquo;Where is the authentication logic?&rdquo; or &ldquo;What does this function do?&rdquo;</p>
            <p><strong>Use when:</strong> You&apos;re exploring unfamiliar code, asking questions, or need a quick explanation.</p>

            <h2>⚡ Standard Mode</h2>
            <p><strong>Cost: 5 Credits</strong> — Your daily driver. A single capable model (e.g., Claude 3.5 Sonnet, GPT-4o, Gemini 2.5 Pro) applies changes directly to your files. The router automatically picks the best model based on task complexity and ELO ratings.</p>
            <p><strong>Use when:</strong> Regular coding tasks — fixing bugs, adding features, writing tests, refactoring.</p>

            <h2>🎯 Ensemble Mode</h2>
            <p><strong>Cost: 25 Credits</strong> — The quality maximizer. Your prompt is dispatched to <strong>3 different AI models simultaneously</strong>. Each model works in isolation, producing its own diff. An impartial <strong>Arbiter Model</strong> then:</p>
            <ol>
                <li>Reads all three solutions</li>
                <li>Scores each one on correctness, completeness, code quality, and security</li>
                <li>Picks the winner with evidence-backed reasoning</li>
                <li>Optionally cherry-picks the best parts from each solution</li>
            </ol>
            <p>The losing models&apos; ELO ratings drop; the winner&apos;s rises. Over time, the system learns which models to pick for which kinds of tasks.</p>
            <p><strong>Use when:</strong> The task is important and you want the provably best solution. Bug fixes in production code, security-sensitive changes, complex algorithmic work.</p>

            <h2>🏗️ Architect Mode</h2>
            <p><strong>Cost: 100 Credits</strong> — For complex, multi-stage feature builds. Architect mode operates in two phases:</p>
            <p><strong>Phase 1 — Plan:</strong> The AI generates a detailed implementation plan with numbered steps, files to modify, and rationale. You review and approve the plan before any code is written.</p>
            <p><strong>Phase 2 — Execute:</strong> The AI implements each step in the plan, verifying in a sandbox as it goes. Only the final, tested branch is presented to you.</p>
            <p><strong>Use when:</strong> Building entire features from scratch, large refactors, multi-file architectural changes.</p>

            <h2>⚔️ Battle Mode</h2>
            <p><strong>Cost: 25 Credits</strong> — Two state-of-the-art models go head-to-head. You see their strategies side-by-side in a split-screen diff and manually select the winner. The winning model gets an ELO boost.</p>
            <p><strong>Use when:</strong> Edge-case algorithms, performance optimizations, or when you want to see fundamentally different approaches to the same problem.</p>

            <h2>🔒 Single Provider Modes</h2>
            <p><strong>Cost: 5 Credits</strong> — Lock execution to a specific AI provider family. Instead of letting the router choose across all available models, you restrict to one vendor:</p>
            <ul>
                <li><code>SINGLE_MODEL_OPENAI</code> — Only OpenAI models</li>
                <li><code>SINGLE_MODEL_ANTHROPIC</code> — Only Anthropic models</li>
                <li><code>SINGLE_MODEL_GOOGLE</code> — Only Google models</li>
            </ul>
            <p>The system still auto-selects the best model within that family based on complexity and ELO ratings.</p>
            <p><strong>Use when:</strong> You have a corporate policy restricting which AI providers you can use, or you strongly prefer a specific vendor&apos;s coding style.</p>

            <h2>Switching Modes</h2>
            <p>Press <code>Ctrl+Q</code> to open the Quality Tier selector, or set your default in settings (<code>Ctrl+,</code>). You can also set a mode per-project in <code>.gptcgt/config.toml</code>.</p>
        </>
    );
}
