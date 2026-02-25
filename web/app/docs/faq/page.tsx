import Link from "next/link";

export const metadata = { title: "FAQ — gptcgt Docs" };

export default function DocsFAQ() {
    return (
        <>
            <h1>Frequently Asked Questions</h1>

            <h2>Is my code sent to servers to train AI?</h2>
            <p>No. When you use Managed Credits, we rely on OpenAI API and Anthropic API endpoints with zero-data-retention agreements. We do not use user data, prompts, or code to train models. See the <Link href="/legal/privacy">Privacy Policy</Link>.</p>

            <h2>What happens if the AI deletes my files?</h2>
            <p>We heavily recommend using git. The IDE tracks workspace diffs, but the AI is capable of utilizing the `delete_file` tool if instructed. Always commit changes before initiating high-impact Architect or Ensemble operations.</p>

            <h2>Why not just use an AI Editor like Cursor?</h2>
            <p>Cursor is excellent, but it binds you to a VSCode fork. gptcgt brings AI agentic orchestration natively into your shell. It operates where your scripts and servers run, providing deep, sandboxed visibility over multi-model reasoning without the GUI overhead.</p>

            <h2>How do I cancel my subscription?</h2>
            <p>Type <code>/billing</code> inside the desktop terminal, or visit the Accounts page on this dashboard. Due to our tight Stripe integration, cancellation and downward plan migrations take effect immediately the following billing cycle.</p>
        </>
    );
}
