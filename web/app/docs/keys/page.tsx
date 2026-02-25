export const metadata = { title: "API Keys & Auth — gptcgt Docs" };

export default function DocsKeys() {
    return (
        <>
            <h1>API Keys & Auth</h1>
            <p>gptcgt offers two ways to power its AI models: Bring Your Own Keys (Free) or Managed Credits (Subscription).</p>

            <h2>Bring Your Own Keys (BYOK)</h2>
            <p>If you already have API keys with Anthropic, OpenAI, DeepSeek, or Google, you can supply them directly to gptcgt. We store these securely in your operating system&apos;s native keychain (e.g. macOS Keychain, Windows Credential Locker) using the <code>keyring</code> python library.</p>
            <ul>
                <li><strong>Pros</strong>: Only pay providers directly for what you use. Total privacy.</li>
                <li><strong>Cons</strong>: You must handle rate limits and billing across 4+ different providers yourself to use Ensemble or Architect modes effectively.</li>
            </ul>

            <h2>Managed Credits (via gptcgt Account)</h2>
            <p>If you prefer a simpler setup, you can subscribe to gptcgt Pro. We handle the api keys and route queries through our LiteLLM proxy boundary. You simply purchase a single bucket of &quot;Credits&quot; that work seamlessly across all models.</p>
            <ul>
                <li>Type <code>/login</code> in the app to authenticate.</li>
                <li>Type <code>/credits</code> to check your balance.</li>
                <li>Type <code>/billing</code> to visit your web dashboard.</li>
            </ul>
        </>
    );
}
