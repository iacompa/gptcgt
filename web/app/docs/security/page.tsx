export const metadata = { title: "Security & Safety — gptcgt Docs" };

export default function DocsSecurity() {
    return (
        <>
            <h1>Security &amp; Safety</h1>
            <p>gptcgt is designed with the principle that <strong>AI agents should never be able to harm your system</strong>. Multiple independent safety mechanisms work together to ensure the AI stays within boundaries.</p>

            <h2>Workspace Sandboxing</h2>
            <p>Every file operation in gptcgt goes through the <strong>Workspace</strong> security boundary. This is a singleton gatekeeper that:</p>
            <ul>
                <li><strong>Resolves all paths</strong> — Including symlinks and <code>../</code> traversals</li>
                <li><strong>Rejects escapes</strong> — Any path outside your project root raises a <code>WorkspaceEscapeError</code></li>
                <li><strong>Logs violations</strong> — Attempted escapes are logged at CRITICAL level</li>
            </ul>
            <p>This means the AI literally cannot read, write, or delete files outside your project directory. No exceptions.</p>

            <h2>Code Security Scanning</h2>
            <p>Every code change the AI generates is automatically scanned before being presented to you. Three scanning layers run in sequence:</p>

            <h3>Layer 1 — Custom Regex (Instant)</h3>
            <p>Built-in patterns catch common security issues immediately, no external tools needed:</p>
            <ul>
                <li>SQL injection via f-strings, .format(), or string concatenation (CWE-89)</li>
                <li>Command injection via <code>os.system()</code> or <code>subprocess.run(shell=True)</code> (CWE-78)</li>
                <li>Cross-site scripting via innerHTML or dangerouslySetInnerHTML (CWE-79)</li>
                <li>Hardcoded API keys, passwords, and secrets (CWE-798)</li>
                <li>Path traversal via <code>open(user_input)</code> (CWE-22)</li>
                <li>Use of <code>eval()</code>, <code>exec()</code>, or <code>pickle.loads()</code> (CWE-502)</li>
                <li>Weak cryptography (<code>md5</code>, <code>sha1</code>, <code>DES</code>)</li>
            </ul>

            <h3>Layer 2 — Semgrep (2-5 seconds)</h3>
            <p>If Semgrep is installed, OWASP Top 10 and language-specific rules are run against the changed files.</p>

            <h3>Layer 3 — Language Scanners</h3>
            <p>Bandit for Python, ESLint security plugins for JavaScript, and similar tools are invoked if available.</p>

            <h2>Security Badge System</h2>
            <p>Every change gets a badge:</p>
            <ul>
                <li>🟢 <strong>CLEAN</strong> — No security issues detected. Proceed normally.</li>
                <li>🟡 <strong>WARNING</strong> — Potential issues found. Details shown, you decide whether to apply.</li>
                <li>🔴 <strong>BLOCKED</strong> — Critical vulnerability. The AI is asked to auto-fix before presenting to you.</li>
            </ul>

            <h3>Auto-Fix Flow for BLOCKED Changes</h3>
            <ol>
                <li>Critical issue found → the finding is sent back to the AI with a targeted fix request</li>
                <li>AI generates a fixed version → re-scan</li>
                <li>If clean → present with &ldquo;Security issue auto-fixed&rdquo; note</li>
                <li>If still blocked after 2 attempts → present with RED warning, you manually acknowledge</li>
            </ol>

            <h2>E2B Sandbox Execution</h2>
            <p>Tests and verification run in <strong>isolated Firecracker microVMs</strong> via E2B (the same technology behind AWS Lambda). This means:</p>
            <ul>
                <li>Test code cannot access your file system</li>
                <li>150ms cold start, $0.083/hr (~$0.002 per verification)</li>
                <li>Pre-built templates for Python, TypeScript, Rust, Go</li>
            </ul>
            <p>If E2B is not configured (no API key), the system falls back to local-only verification: syntax checks via tree-sitter and your local linter.</p>

            <h2>LSP Cross-File Reference Verification</h2>
            <p>After an AI agent renames a function or modifies a symbol, the LSP client checks that <strong>all references across the project</strong> have been updated. This catches the #1 complaint about AI coding tools: broken multi-file edits.</p>
            <pre><code>{`Example:
  Agent renames process_payment() in payments.py
  → LSP finds references in orders.py:42, checkout.py:18, tests/test_payments.py:7
  → Checks: did the agent update all three?
  → orders.py:42 — UPDATED ✓
  → checkout.py:18 — MISSED ✗
  → Result: incomplete, missed reference at checkout.py:18`}</code></pre>

            <h2>Sensitive Data Protection</h2>
            <p>All log output (file logs, debug logs, UI) passes through a <strong>SensitiveDataFilter</strong> that scrubs:</p>
            <ul>
                <li>OpenAI keys (<code>sk-...</code>)</li>
                <li>Anthropic keys (<code>sk-ant-...</code>)</li>
                <li>Google keys (<code>AIza...</code>)</li>
                <li>xAI keys (<code>xai-...</code>)</li>
                <li>Groq keys (<code>gsk_...</code>)</li>
                <li>Generic bearer tokens and passwords</li>
            </ul>
            <p>This filter is applied to every log handler, including traceback output. Even if an error occurs while processing your API key, it won&apos;t appear in the log files.</p>

            <h2>Crash Recovery</h2>
            <p>If gptcgt exits unexpectedly:</p>
            <ul>
                <li>A PID-locked <code>running.lock</code> detects crashes vs. concurrent instances</li>
                <li>Application state is atomically saved via temp file + rename (prevents corruption)</li>
                <li>Unapplied diffs are backed up and can be restored on next launch</li>
                <li>Signal handlers (SIGTERM, SIGINT) ensure clean shutdown when killed</li>
            </ul>

            <h2>Content Filtering (Proxy)</h2>
            <p>For Managed Credit users, requests pass through a server-side content filter that blocks:</p>
            <ul>
                <li>Prompt injection attempts (&ldquo;ignore previous instructions&rdquo;, &ldquo;enter god mode&rdquo;)</li>
                <li>Harmful content requests</li>
                <li>Credential extraction attempts</li>
            </ul>
        </>
    );
}
