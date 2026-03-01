export const metadata = { title: "ELO Arena — gptcgt Docs" };

export default function DocsEloArena() {
    return (
        <>
            <h1>ELO Arena</h1>
            <p>gptcgt includes a built-in <strong>competitive ranking system</strong> for AI models. Every time models compete in Ensemble or Battle mode, their ELO ratings are updated — just like chess rankings. Over time, the system learns which models perform best and routes tasks to them more often.</p>

            <h2>How ELO Works</h2>
            <p>The ELO rating system was originally designed for chess. In gptcgt, it works the same way:</p>
            <ul>
                <li>Every model starts at <strong>1200 ELO</strong></li>
                <li>When a model wins a head-to-head comparison (Ensemble or Battle), its rating goes up</li>
                <li>The losing model&apos;s rating goes down</li>
                <li>If a weak model beats a strong model, the point swing is larger (upset bonus)</li>
                <li>If a strong model beats a weak model, the swing is smaller (expected outcome)</li>
            </ul>

            <h2>When Matches Happen</h2>
            <ul>
                <li><strong>Ensemble Mode</strong> — 3 models compete. The Arbiter picks the winner. The 2 losers each take an ELO hit.</li>
                <li><strong>Battle Mode</strong> — 2 models compete. You manually select the winner.</li>
            </ul>

            <h2>Multi-Way Dampening</h2>
            <p>In Ensemble mode where 1 model beats 3, the winner&apos;s ELO gain is dampened to prevent hyper-inflation. The system divides the delta by a factor of the number of losers to keep ratings stable over time.</p>

            <h2>How Routing Uses ELO</h2>
            <p>When the router selects a model for your task, it uses ELO as a tiebreaker:</p>
            <ol>
                <li>First, it filters models by your quality tier (Standard, Max, etc.)</li>
                <li>Then, it filters by task complexity</li>
                <li>Among the remaining candidates, <strong>higher ELO models are preferred</strong></li>
                <li>Cost is used as a secondary tiebreaker — if two models have similar ELO, the cheaper one wins</li>
            </ol>
            <p>This means the more you use gptcgt, the smarter its model selection becomes — tailored to your specific projects and coding style.</p>

            <h2>Leaderboard</h2>
            <p>ELO ratings, match counts, win rates, and total spend per model are stored in a SQLite database at <code>~/.gptcgt/elo.db</code>. The leaderboard is visible in the application&apos;s settings panel.</p>

            <h2>Data Tracked</h2>
            <div className="not-prose overflow-x-auto my-4">
                <table className="w-full text-sm text-gray-300">
                    <thead>
                        <tr className="border-b border-gray-800 text-left text-gray-400">
                            <th className="py-2 pr-4">Field</th>
                            <th className="py-2 pr-4">Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">ELO Rating</td><td className="py-2 pr-4">Current competitive rating</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Matches Won</td><td className="py-2 pr-4">Total head-to-head wins</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Matches Lost</td><td className="py-2 pr-4">Total head-to-head losses</td></tr>
                        <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-white">Win Rate</td><td className="py-2 pr-4">Percentage of matches won</td></tr>
                        <tr><td className="py-2 pr-4 text-white">Total Spent</td><td className="py-2 pr-4">Cumulative $ spent on this model</td></tr>
                    </tbody>
                </table>
            </div>
        </>
    );
}
