export const metadata = { title: "API Keys & Auth — gptcgt Docs" };

export default function DocsKeys() {
    return (
        <>
            <h1>API Keys &amp; Auth</h1>
            <p>gptcgt offers two ways to power its AI models. You choose which approach fits your workflow — or use both.</p>

            <h2>Option 1: Bring Your Own Keys (BYOK) — Free</h2>
            <p>Supply your own API keys from any supported provider. gptcgt stores them securely in your operating system&apos;s native keychain (macOS Keychain, Windows Credential Locker, Linux Secret Service) via the <code>keyring</code> Python library. Keys never touch disk in plaintext.</p>

            <h3>Supported Providers</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Provider</th><th className="py-2 pr-4">Env Variable</th><th className="py-2">Notable Models</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">OpenAI</td><td className="py-2 pr-4 font-mono text-xs">OPENAI_API_KEY</td><td className="py-2">GPT-4o, o3, o1</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Anthropic</td><td className="py-2 pr-4 font-mono text-xs">ANTHROPIC_API_KEY</td><td className="py-2">Claude 3.5 Sonnet, Claude 3 Opus</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Google</td><td className="py-2 pr-4 font-mono text-xs">GEMINI_API_KEY</td><td className="py-2">Gemini 2.5 Pro, Gemini 2.5 Flash</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">DeepSeek</td><td className="py-2 pr-4 font-mono text-xs">DEEPSEEK_API_KEY</td><td className="py-2">DeepSeek V3, DeepSeek Coder</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">xAI</td><td className="py-2 pr-4 font-mono text-xs">XAI_API_KEY</td><td className="py-2">Grok 2</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Mistral</td><td className="py-2 pr-4 font-mono text-xs">MISTRAL_API_KEY</td><td className="py-2">Mistral Large</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Groq</td><td className="py-2 pr-4 font-mono text-xs">GROQ_API_KEY</td><td className="py-2">LLaMA 3 (ultra-fast inference)</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Cohere</td><td className="py-2 pr-4 font-mono text-xs">COHERE_API_KEY</td><td className="py-2">Command R+</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">OpenRouter</td><td className="py-2 pr-4 font-mono text-xs">OPENROUTER_API_KEY</td><td className="py-2">Access to 200+ models via one key</td></tr>
                        <tr><td className="py-2 pr-4 text-white">Custom</td><td className="py-2 pr-4 font-mono text-xs">CUSTOM_API_KEY</td><td className="py-2">Ollama, vLLM, any OpenAI-compatible API</td></tr>
                    </tbody>
                </table>
            </div>

            <p><strong>Pros:</strong> Only pay providers directly. Total privacy. No subscription needed.</p>
            <p><strong>Cons:</strong> You manage rate limits and billing across multiple providers yourself. Ensemble/Architect modes require keys from multiple providers.</p>

            <h3>BYOK Safety Limits</h3>
            <p>Even with your own keys, gptcgt enforces spend protection:</p>
            <pre><code>{`# In ~/.gptcgt/global.toml
daily_spend_limit = 10.0    # $10/day hard stop
max_spend_per_task = 2.0    # $2 max per individual task
max_tokens_per_task = 500000 # 500K token cap per task`}</code></pre>

            <h2>Option 2: Managed Credits (Subscription)</h2>
            <p>Sign up for gptcgt Pro and get a single bucket of <strong>Credits</strong> that work seamlessly across all providers. We handle API keys, routing, rate limiting, and billing through our LiteLLM proxy.</p>
            <ol>
                <li>Type <code>/login</code> in the app to start the WorkOS device flow</li>
                <li>Authorize in your browser</li>
                <li>You&apos;re in — credits are automatically used for all tasks</li>
            </ol>

            <h3>Credit Costs by Mode</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Mode</th><th className="py-2 pr-4">Credits</th><th className="py-2">~ Dollar Cost</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4">Scout</td><td className="py-2 pr-4">1</td><td className="py-2">~$0.01</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4">Standard</td><td className="py-2 pr-4">5</td><td className="py-2">~$0.05</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4">Ensemble / Battle</td><td className="py-2 pr-4">25</td><td className="py-2">~$0.25</td></tr>
                        <tr><td className="py-2 pr-4">Architect</td><td className="py-2 pr-4">100</td><td className="py-2">~$1.00</td></tr>
                    </tbody>
                </table>
            </div>

            <h3>Key Commands</h3>
            <ul>
                <li><code>/login</code> — Authenticate with your gptcgt account</li>
                <li><code>/logout</code> — Sign out</li>
                <li><code>/credits</code> — Check your remaining balance</li>
                <li><code>/billing</code> — Open the web dashboard for subscription management</li>
            </ul>

            <h2>Verifying Key Health</h2>
            <p>Run <code>/status</code> at any time to check the health and latency of all configured providers. gptcgt will test each API key with a minimal health-check request using the cheapest available model for that provider.</p>
        </>
    );
}
