export const metadata = { title: "Operation Modes — gptcgt Docs" };

export default function DocsModes() {
    return (
        <>
            <h1>Operation Modes</h1>
            <p>gptcgt uniquely separates agent behaviors into 5 distinct operational modes, allowing you to optimize for speed, cost, or profound reasoning depending on the task at hand.</p>

            <h2>Scout Mode</h2>
            <p><strong>Cost: 1 Credit.</strong> A high-speed, lightweight agent optimized to navigate unfamiliar codebases. It reads directory structures, builds AST maps, and answers &quot;where do I find X?&quot; without making edits.</p>

            <h2>Standard Mode</h2>
            <p><strong>Cost: 5 Credits.</strong> Your daily driver. A single, capable model (e.g. Claude 3.5 Sonnet or GPT-4o) applies changes directly to your files.</p>

            <h2>Ensemble Mode</h2>
            <p><strong>Cost: 25 Credits.</strong> Dispatches your prompt to 3 different models simultaneously. Their isolated changes are collected into PatchSets and presented to an Arbiter Model, which scores the changes and applies the definitively correct solution.</p>

            <h2>Architect Mode</h2>
            <p><strong>Cost: 100 Credits.</strong> For complex, multi-stage feature requests. The Architect drafts a plan, verifies it in a sandbox, loops through implementations, and only presents the final verified branch to the user.</p>

            <h2>Battle Mode</h2>
            <p><strong>Cost: 25 Credits.</strong> Two state-of-the-art models execute your prompt. You are presented with a side-by-side split screen diff of their strategies, and you manually select the winner. Useful for edge-case algorithms.</p>

            <h2>Single Provider Modes</h2>
            <p><strong>Cost: 5 Credits.</strong> Instead of allowing the internal router to arbitrarily select the most cost-efficient model across all providers, you can lock execution to a specific provider family natively (e.g., <code>SINGLE_MODEL_OPENAI</code>, <code>SINGLE_MODEL_ANTHROPIC</code>, <code>SINGLE_MODEL_GOOGLE</code>). The pipeline handles dynamic tier-scaling exclusively using models from that vendor.</p>
        </>
    );
}
