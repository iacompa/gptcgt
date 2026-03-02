export default function AcceptableUsePage() {
    return (
        <div className="relative isolate px-6 py-24 sm:py-32 lg:px-8 max-w-4xl mx-auto">
            <div className="mx-auto max-w-3xl text-base leading-7 text-gray-300">
                <p className="text-base font-semibold leading-7 text-indigo-400">gptcgt</p>
                <h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">Acceptable Use Policy</h1>
                <p className="mt-6 text-xl leading-8 text-gray-200">
                    Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                </p>
                <div className="mt-10 max-w-2xl text-gray-300">
                    <p>
                        This Acceptable Use Policy defines the parameters under which you may use the gptcgt terminal client, our proxy APIs, and our web services. Adherence to this policy is mandatory.
                    </p>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">1. Prohibited Content & Use Cases</h2>
                    <p className="mt-6">
                        You may not use gptcgt to generate, refine, or facilitate any of the following:
                    </p>
                    <ul className="mt-4 list-disc space-y-2 pl-8">
                        <li><strong>Malware & Exploits:</strong> Generating viruses, ransomware, or zero-day exploits intended to compromise unauthorized systems.</li>
                        <li><strong>Illegal Activities:</strong> Code or configurations designed to harass, defraud, steal data, or bypass legal DRM/access controls.</li>
                        <li><strong>Spam Automation:</strong> Building systems designed primarily for mass, unsolicited communication.</li>
                        <li><strong>Harmful Material:</strong> Content that Promotes violence, self-harm, child exploitation, or illegal substances.</li>
                    </ul>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">2. Abuse of the Pro Tier Strategy</h2>
                    <p className="mt-6">
                        If you are utilizing our Managed Credits tier (routing requests through our proxy), the following actions will result in immediate termination:
                    </p>
                    <ul className="mt-4 list-disc space-y-2 pl-8">
                        <li><strong>Account Sharing:</strong> Reselling, redistributing, or sharing your account credentials so multiple, unassociated users can deplete your quota.</li>
                        <li><strong>System Subversion:</strong> Attempting to scrape, reverse-engineer, DDoS, or bypass the rate-limits implemented on our API endpoints.</li>
                        <li><strong>Automated Scraping:</strong> Using headless browsers or automated bots to interact with our web dashboard for the purpose of credit manipulation or data exfiltration.</li>
                    </ul>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">3. Third-Party Downstream Rules</h2>
                    <p className="mt-6">
                        Because gptcgt acts as a conduit to models like Claude, GPT-4, and Gemini, you are simultaneously bound by their respective usage policies.
                        If Anthropic or OpenAI flags a prompt sent through our proxy as a violation of their safety guidelines, we are legally obligated to enforce that decision and may suspend your account to protect our API access.
                    </p>

                    <h2 className="mt-16 text-2xl font-bold tracking-tight text-white">4. Enforcement</h2>
                    <p className="mt-6">
                        We reserve the right to monitor account usage patterns (e.g., volume spikes, connection origins) to detect abuse. We do not monitor your source code, but we do monitor macro-level API interaction behaviors.
                        Violations of this Acceptable Use Policy may lead to immediate suspension or permanent termination of your account, without refund.
                    </p>
                </div>
            </div>
        </div>
    );
}
