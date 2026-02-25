// Phase 6: Part C — Acceptable Use Policy
// Created: Phase 6 Polish & Launch Prep

export const metadata = { title: "Acceptable Use Policy — gptcgt" };

export default function AcceptableUsePolicy() {
    return (
        <>
            <h1>Acceptable Use Policy</h1>
            <p><strong>Last updated:</strong> February 2026</p>

            <h2>1. Allowed Activities</h2>
            <ul>
                <li>✅ Coding software and applications.</li>
                <li>✅ Assisting with bugs, linting, debugging, and system administration.</li>
                <li>✅ Learning or exploring computer science topics.</li>
                <li>✅ Refactoring, modernizing, or testing existing codebases.</li>
            </ul>

            <h2>2. Strictly Prohibited</h2>
            <ul>
                <li>❌ <strong>CSAM</strong>: Accessing, transmitting, generating, or asking about Child Sexual Abuse Material.</li>
                <li>❌ <strong>Malware</strong>: Generating explicit exploits, viruses, trojans, ransomware, or sophisticated spyware.</li>
                <li>❌ <strong>Jailbreaking</strong>: Supplying systematic instructions aiming to bypass our proxy moderation boundary or the AI providers’ native safety guidelines.</li>
                <li>❌ <strong>Illegal Surveillance</strong>: Building systematic tracking software or doxxing engines.</li>
            </ul>

            <h2>3. Consequences and Enforcement</h2>
            <p>Violations trigger tiered responses by our automated moderation engine:</p>
            <ul>
                <li><strong>Warning</strong>: For borderline or unintended prohibited outputs.</li>
                <li><strong>Suspension</strong>: Repeated minor offenses may suspend API access for fixed durations.</li>
                <li><strong>Permanent Ban</strong>: Overtly malicious behavior or CSAM inquiries result in zero-tolerance bans and reports to appropriate authorities.</li>
            </ul>
        </>
    );
}
