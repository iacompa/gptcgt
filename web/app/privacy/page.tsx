export default function PrivacyPolicyPage() {
    return (
        <div className="relative isolate px-6 py-24 sm:py-32 lg:px-8 max-w-4xl mx-auto">
            <div className="mx-auto max-w-3xl text-base leading-7 text-gray-300">
                <p className="text-base font-semibold leading-7 text-indigo-400">gptcgt</p>
                <h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">Privacy Policy</h1>
                <p className="mt-6 text-xl leading-8 text-gray-200">
                    Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                </p>
                <div className="mt-10 max-w-2xl text-gray-300">
                    <p>
                        At gptcgt (operated by IA Compa LLC), privacy is treated as a fundamental feature, not an afterthought.
                        As a professional developer tool bridging your local environment and cloud AI providers, we have architected
                        our systems to minimize data collection and maximize your control over your own code.
                    </p>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">1. Information We Collect</h2>
                    <ul className="mt-8 space-y-8 text-gray-300">
                        <li className="flex gap-x-3">
                            <span><strong className="font-semibold text-white">Account Information:</strong> We collect your email address and basic profile information when you register for an account to provide you with secure access to our services.</span>
                        </li>
                        <li className="flex gap-x-3">
                            <span><strong className="font-semibold text-white">Usage Data:</strong> We collect aggregated, anonymous telemetry regarding model execution times, success rates, and basic CLI interactions (e.g., "User ran a prompt using Claude 3.5 Sonnet"). <strong className="text-indigo-400">We do not collect the contents of your code, your prompts, or your AI responses.</strong></span>
                        </li>
                        <li className="flex gap-x-3">
                            <span><strong className="font-semibold text-white">API Keys:</strong> Under the "Bring Your Own Keys" (BYOK) model, your provider API keys (OpenAI, Anthropic, etc.) are stored exclusively on your local machine using your operating system's secure keychain. They are never transmitted to or stored on our servers.</span>
                        </li>
                    </ul>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">2. How Your Code is Handled</h2>
                    <p className="mt-6">
                        When you use gptcgt, your code and prompts are sent directly from your terminal to the respective AI provider (OpenAI, Anthropic, Google, etc.).
                        Our backend systems are utilized strictly for routing (if using our proxy/managed credits), billing, and licensing verification.
                    </p>
                    <div className="mt-8 rounded-xl bg-gray-900/50 p-6 ring-1 ring-inset ring-gray-800">
                        <h3 className="text-sm font-semibold text-white">Zero-Retention Policy</h3>
                        <p className="mt-2 text-sm text-gray-400">
                            When using our Managed Credits (Pro Tier), your prompts and code pass through our proxy for authentication and accounting, but are never logged, stored, or used for training our own models. Your data passes in memory and is discarded immediately after the provider responds.
                        </p>
                    </div>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">3. Third-Party Services</h2>
                    <p className="mt-6">
                        We integrate with third-party AI providers. When you submit a prompt, you are subject to that specific provider's privacy policy and terms of service. We currently support:
                    </p>
                    <ul className="mt-4 list-disc space-y-2 pl-8">
                        <li>OpenAI (ChatGPT models)</li>
                        <li>Anthropic (Claude models)</li>
                        <li>Google (Gemini models)</li>
                        <li>xAI (Grok models)</li>
                        <li>Local models (Ollama - processes entirely on your machine)</li>
                    </ul>


                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">4. Data Security</h2>
                    <p className="mt-6">
                        We implement strict security measures to protect your account data. All communications between the gptcgt CLI and our servers are encrypted using TLS. Your local API keys are secured by your native OS credential manager (macOS Keychain, Windows Credential Manager, or Linux Secret Service).
                    </p>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">5. Your Privacy Rights</h2>
                    <p className="mt-6">
                        You have the right to access, update, or delete your account information at any time. If you wish to permanently delete your account and all associated billing unformation, please contact us at support@gptcgt.ai.
                    </p>
                </div>
            </div>
        </div>
    );
}
