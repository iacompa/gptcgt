"use client";

import { useState, useEffect } from "react";
import { fetchAPI } from "@/lib/api";
import { UsageChart } from "@/components/usage-chart";

export default function UsagePage() {
    const [events, setEvents] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    // Stats
    const [totalCredits, setTotalCredits] = useState(0);
    const [totalRequests, setTotalRequests] = useState(0);
    const [totalSandboxRuns, setTotalSandboxRuns] = useState(0);
    const [chartData, setChartData] = useState<any[]>([]);

    useEffect(() => {
        loadUsage();
    }, []);

    const loadUsage = async () => {
        try {
            // In a real app we'd pass start_date and end_date
            const data = await fetchAPI("/usage/");
            setEvents(data);

            // Calculate Stats
            let credits = 0;
            let requests = data.length;
            let sandboxRuns = 0;

            const chartMap = new Map<string, number>();

            data.forEach((evt: any) => {
                credits += evt.credits_consumed;
                if (evt.task_mode === "sandbox" || (evt.models_used && evt.models_used.includes("e2b_sandbox_run"))) {
                    sandboxRuns++;
                }

                // Group by day out of ISO string
                const day = evt.created_at.split('T')[0];
                chartMap.set(day, (chartMap.get(day) || 0) + evt.credits_consumed);
            });

            setTotalCredits(credits);
            setTotalRequests(requests);
            setTotalSandboxRuns(sandboxRuns);

            // Format for recharts
            const cData = Array.from(chartMap.entries())
                .map(([date, credits]) => ({ date, credits }))
                .sort((a, b) => a.date.localeCompare(b.date)); // chronological

            setChartData(cData);

        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <div className="flex justify-between items-end mb-6">
                <div>
                    <h1 className="text-2xl font-bold">Usage Analytics</h1>
                    <p className="text-gray-400 mt-1">Monitor your pipeline execution costs and token consumption</p>
                </div>
                <div className="flex gap-2">
                    <select className="bg-gray-900 border border-gray-800 rounded-md px-3 py-1.5 text-sm text-gray-300">
                        <option>Last 7 Days</option>
                        <option>Last 30 Days</option>
                        <option>Current Month</option>
                    </select>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <p className="text-sm text-gray-400 mb-1">Total Proxy Credits</p>
                    <p className="text-2xl font-bold">{totalCredits.toLocaleString()}</p>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <p className="text-sm text-gray-400 mb-1">Total Pipeline Executions</p>
                    <p className="text-2xl font-bold">{totalRequests.toLocaleString()}</p>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <p className="text-sm text-gray-400 mb-1">Sandbox Executions</p>
                    <p className="text-2xl font-bold">{totalSandboxRuns.toLocaleString()}</p>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 relative overflow-hidden">
                    <div className="relative z-10">
                        <p className="text-sm text-gray-400 mb-1">Average Cost Per Task</p>
                        <p className="text-2xl font-bold">
                            {totalRequests > 0 ? (totalCredits / totalRequests).toFixed(1) : 0} <span className="text-sm font-normal text-gray-500">cr</span>
                        </p>
                    </div>
                </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
                <h3 className="font-bold mb-6">Credit Consumption</h3>
                {loading ? (
                    <div className="h-64 flex items-center justify-center text-gray-500 text-sm">Loading chart data...</div>
                ) : (
                    <UsageChart data={chartData} />
                )}
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-gray-800 text-gray-400">
                        <tr>
                            <th className="px-6 py-3 font-medium">TIMESTAMP</th>
                            <th className="px-6 py-3 font-medium">TASK MODE</th>
                            <th className="px-6 py-3 font-medium">MODELS USED</th>
                            <th className="px-6 py-3 font-medium text-right">INPUT TOK</th>
                            <th className="px-6 py-3 font-medium text-right">OUTPUT TOK</th>
                            <th className="px-6 py-3 font-medium text-right">CREDITS REC</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {loading ? (
                            <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-500">Loading events...</td></tr>
                        ) : events.length === 0 ? (
                            <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-500">No usage recorded within timeframe.</td></tr>
                        ) : (
                            events.map((evt) => (
                                <tr key={evt.id} className="hover:bg-gray-800/50">
                                    <td className="px-6 py-3 text-gray-300">
                                        {new Date(evt.created_at).toLocaleString(undefined, {
                                            month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
                                        })}
                                    </td>
                                    <td className="px-6 py-3 capitalize">{evt.task_mode}</td>
                                    <td className="px-6 py-3">
                                        <div className="flex gap-1 flex-wrap">
                                            {evt.models_used && evt.models_used.map((m: string) => (
                                                <span key={m} className="bg-gray-800 text-gray-400 px-2 py-0.5 rounded text-xs">{m}</span>
                                            ))}
                                        </div>
                                    </td>
                                    <td className="px-6 py-3 text-right text-gray-400">{evt.input_tokens?.toLocaleString() || 0}</td>
                                    <td className="px-6 py-3 text-right text-gray-400">{evt.output_tokens?.toLocaleString() || 0}</td>
                                    <td className="px-6 py-3 text-right font-medium text-indigo-400">{evt.credits_consumed}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
