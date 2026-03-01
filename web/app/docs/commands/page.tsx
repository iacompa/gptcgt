export const metadata = { title: "Commands & Shortcuts — gptcgt Docs" };

export default function DocsCommands() {
    return (
        <>
            <h1>Commands &amp; Shortcuts</h1>
            <p>gptcgt is designed for keyboard-first efficiency. Every feature is accessible without a mouse.</p>

            <h2>Slash Commands</h2>
            <p>Type these in the chat input to trigger actions:</p>

            <h3>Core</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Command</th><th className="py-2">Description</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/help</td><td className="py-2">Show the help overlay with all commands and shortcuts</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/setup</td><td className="py-2">Re-run the onboarding wizard (reset keys, theme, tier)</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/clear</td><td className="py-2">Clear the chat display history</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/status</td><td className="py-2">Check all AI provider health, latency, and key status</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/version</td><td className="py-2">Show application version</td></tr>
                        <tr><td className="py-2 pr-4 text-indigo-300 font-mono">/models</td><td className="py-2">List all available models and their ELO ratings</td></tr>
                    </tbody>
                </table>
            </div>

            <h3>Account &amp; Billing</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Command</th><th className="py-2">Description</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/login</td><td className="py-2">Start WorkOS device flow authentication</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/logout</td><td className="py-2">Sign out of your managed credits account</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/credits</td><td className="py-2">Check remaining managed credits balance</td></tr>
                        <tr><td className="py-2 pr-4 text-indigo-300 font-mono">/billing</td><td className="py-2">Open the web dashboard to manage subscriptions</td></tr>
                    </tbody>
                </table>
            </div>

            <h3>Workspace &amp; Git</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Command</th><th className="py-2">Description</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/diff</td><td className="py-2">Show the current pending diff before applying</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-indigo-300 font-mono">/undo</td><td className="py-2">Revert the last applied change</td></tr>
                        <tr><td className="py-2 pr-4 text-indigo-300 font-mono">/context</td><td className="py-2">Show what files are in the AI&apos;s context window</td></tr>
                    </tbody>
                </table>
            </div>

            <h2>Global Keyboard Shortcuts</h2>
            <p>These work from anywhere in the application:</p>

            <h3>Navigation</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Shortcut</th><th className="py-2">Action</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Tab</td><td className="py-2">Cycle focus between panels</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Ctrl+P</td><td className="py-2">Command palette — search workspace files</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Ctrl+B</td><td className="py-2">Toggle the left File Tree panel</td></tr>
                        <tr><td className="py-2 pr-4 font-mono text-white">Ctrl+J</td><td className="py-2">Toggle the right Chat panel</td></tr>
                    </tbody>
                </table>
            </div>

            <h3>Configuration</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Shortcut</th><th className="py-2">Action</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Ctrl+Q</td><td className="py-2">Open Quality Tier selector (Scout/Standard/Ensemble/Architect)</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Ctrl+T</td><td className="py-2">Cycle through color themes</td></tr>
                        <tr><td className="py-2 pr-4 font-mono text-white">Ctrl+,</td><td className="py-2">Open application settings overlay</td></tr>
                    </tbody>
                </table>
            </div>

            <h3>Task Control</h3>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead><tr className="border-b border-gray-800 text-left text-gray-400"><th className="py-2 pr-4">Shortcut</th><th className="py-2">Action</th></tr></thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Escape</td><td className="py-2">Cancel current AI generation</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 font-mono text-white">Enter</td><td className="py-2">Accept the proposed diff</td></tr>
                        <tr><td className="py-2 pr-4 font-mono text-white">Ctrl+C</td><td className="py-2">Force cancel / exit</td></tr>
                    </tbody>
                </table>
            </div>
        </>
    );
}
