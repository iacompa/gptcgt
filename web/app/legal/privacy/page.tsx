// Phase 6: Part C — Privacy Policy
// Created: Phase 6 Polish & Launch Prep

export const metadata = { title: "Privacy Policy — gptcgt" };

export default function PrivacyPolicy() {
    return (
        <>
            <h1>Privacy Policy</h1>
            <p><strong>Last updated:</strong> February 2026</p>

            <h2>1. What We Collect</h2>
            <p>We collect essential account information (e.g., your email, name), technical data, and anonymized usage metadata to operate the service. All billing and payment details are securely managed and collected exclusively through Stripe.</p>

            <h2>2. What We DO NOT Collect</h2>
            <p>Privacy is central to our terminal IDE design. We <strong>do not</strong> log, store, or warehouse:</p>
            <ul>
                <li>Your source code or files.</li>
                <li>Your chat messages/prompts.</li>
                <li>Your application passwords or local environment variables.</li>
            </ul>

            <h2>3. AI Provider Disclosures</h2>
            <p>When using our Managed Credits, your prompts are transmitted over HTTPS to our downstream partners. You must review their individual privacy practices. Notably:</p>
            <ul>
                <li><strong>Anthropic and OpenAI</strong>: Both providers explicitly stipulate they do not use API data to train their models.</li>
                <li><strong>DeepSeek</strong>: Processes requests on servers based in China. The IDE will warn you globally during your first use of DeepSeek.</li>
                <li><strong>E2B (Execution Sandboxes)</strong>: Code executed within Firecracker MicroVMs operates ephemerally and shuts down immediately upon termination.</li>
            </ul>

            <h2>4. User Rights (GDPR/CCPA)</h2>
            <p>You may request a copy of your personal data, restrict its use, or demand deletion by contacting us. We will honor your requests without prejudice.</p>

            <h2>5. Data Retention</h2>
            <p>Active account data remains for the length of your subscription plus 30 days. Anonymized usage analytics are retained for 12 months. Fraud/abuse blocks are retained for 6 months for security auditing.</p>

            <h2>6. Contact Us</h2>
            <p>For questions or requests, please contact us at: <code>privacy@gptcgt.ai</code>.</p>
        </>
    );
}
