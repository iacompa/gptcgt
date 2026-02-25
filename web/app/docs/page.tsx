export const metadata = { title: "Documentation — gptcgt" };

export default function DocsOverview() {
    return (
        <>
            <h1>gptcgt Documentation</h1>
            <p>Welcome to the official documentation for gptcgt, the multi-model AI coding terminal. gptcgt transforms your standard terminal environment into an intelligent IDE hooked directly into the world&apos;s most capable Large Language Models.</p>

            <h2>Installation</h2>
            <p>We recommend installing via pipx to avoid global environment conflicts:</p>
            <pre><code>pipx install gptcgt</code></pre>
            <p>Or alternatively, via standard pip:</p>
            <pre><code>pip install gptcgt</code></pre>

            <h2>Quick Start</h2>
            <ol>
                <li>Navigate to your project directory: <code>cd ~/my-project</code></li>
                <li>Launch the TUI: <code>gptcgt</code></li>
                <li>Follow the onboarding wizard to either enter your API keys locally (Free BYOK) or sign in to use Managed Credits for intelligent routing and sandboxing.</li>
                <li>Press <code>Tab</code> or <code>Ctrl+J</code> to focus the chat input, and just type what you want to do.</li>
            </ol>

            <h2>Core Philosophy</h2>
            <p>gptcgt brings the AI into your existing workflow, rather than forcing you into a heavy Electron app. It observes your codebase through TreeSitter tokenization, computes precise context maps, and routes tasks to the best model—transparently logging every cent it spends.</p>
        </>
    );
}
