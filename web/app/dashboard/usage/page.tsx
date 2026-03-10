"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3, Clock3, Filter, Wallet } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/toaster";

const UsageChart = dynamic(
    () => import("@/components/usage-chart").then((module) => module.UsageChart),
    {
        ssr: false,
        loading: () => (
            <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">
                Loading chart...
            </div>
        ),
    }
);

type RangeOption = "7d" | "30d" | "month";

function getRangeWindow(range: RangeOption) {
    const now = new Date();
    if (range === "month") {
        return {
            start_date: new Date(now.getFullYear(), now.getMonth(), 1).toISOString(),
            end_date: now.toISOString(),
        };
    }

    const days = range === "7d" ? 7 : 30;
    return {
        start_date: new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString(),
        end_date: now.toISOString(),
    };
}

function buildChartData(events: any[]) {
    const chartMap = new Map<string, number>();
    events.forEach((event) => {
        const day = event.created_at.split("T")[0];
        chartMap.set(day, (chartMap.get(day) || 0) + event.credits_consumed);
    });
    return Array.from(chartMap.entries())
        .map(([date, credits]) => ({ date, credits }))
        .sort((left, right) => left.date.localeCompare(right.date));
}

export default function UsagePage() {
    const [events, setEvents] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [range, setRange] = useState<RangeOption>("30d");
    const { pushToast } = useToast();

    const loadUsage = useCallback(async (selectedRange: RangeOption) => {
        setLoading(true);
        try {
            const { start_date, end_date } = getRangeWindow(selectedRange);
            const { data, error } = await apiClient.GET("/usage/", {
                params: {
                    query: { start_date, end_date },
                },
            });
            if (error) throw error;
            setEvents((data as any[]) || []);
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Could not load usage",
                description: error.message,
            });
        } finally {
            setLoading(false);
        }
    }, [pushToast]);

    useEffect(() => {
        void loadUsage(range);
    }, [loadUsage, range]);

    const totalCredits = useMemo(
        () => events.reduce((sum, event) => sum + (event.credits_consumed || 0), 0),
        [events]
    );
    const totalRequests = events.length;
    const totalSandboxRuns = useMemo(
        () =>
            events.filter(
                (event) => event.task_mode === "sandbox" || event.models_used?.includes?.("e2b_sandbox_run")
            ).length,
        [events]
    );
    const chartData = useMemo(() => buildChartData(events), [events]);

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="eyebrow">Usage analytics</p>
                        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                            Watch cost and execution volume without leaving the workspace.
                        </h1>
                        <p className="mt-3 max-w-3xl copy-lg">
                            Filter the ledger by time, inspect request history, and spot when sandbox runs or expensive model choices are driving the bill.
                        </p>
                    </div>
                    <div className="flex items-center gap-2 rounded-full border border-[var(--border)] bg-white/75 px-3 py-2">
                        <Filter className="h-4 w-4 text-[var(--accent)]" />
                        <select
                            value={range}
                            onChange={(event) => setRange(event.target.value as RangeOption)}
                            className="bg-transparent text-sm text-slate-900 outline-none"
                        >
                            <option value="7d">Last 7 days</option>
                            <option value="30d">Last 30 days</option>
                            <option value="month">Current month</option>
                        </select>
                    </div>
                </div>
            </section>

            <section className="grid gap-4 md:grid-cols-4">
                <div className="metric-card">
                    <p className="metric-label">Proxy credits</p>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">{totalCredits.toLocaleString()}</p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">Across the selected time range</p>
                </div>
                <div className="metric-card">
                    <p className="metric-label">Executions</p>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">{totalRequests.toLocaleString()}</p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">Total recorded usage events</p>
                </div>
                <div className="metric-card">
                    <p className="metric-label">Sandbox runs</p>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">{totalSandboxRuns.toLocaleString()}</p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">Execution events routed through the sandbox</p>
                </div>
                <div className="metric-card">
                    <p className="metric-label">Average cost</p>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                        {totalRequests > 0 ? (totalCredits / totalRequests).toFixed(1) : "0.0"}
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">Credits per recorded task</p>
                </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="panel p-6">
                    <div className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5 text-[var(--accent)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Credit consumption over time</h2>
                    </div>
                    <div className="mt-5">
                        {loading ? (
                            <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">Loading chart data...</div>
                        ) : (
                            <UsageChart data={chartData} />
                        )}
                    </div>
                </div>

                <div className="panel p-6">
                    <div className="flex items-center gap-2">
                        <Wallet className="h-5 w-5 text-[var(--amber)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">How to read this</h2>
                    </div>
                    <div className="mt-5 space-y-4 text-sm text-[var(--text-muted)]">
                        <div className="panel-muted p-4">
                            Credit totals are derived from the immutable usage ledger, not inferred from wallet balance changes.
                        </div>
                        <div className="panel-muted p-4">
                            Sandbox runs are counted when the task mode is explicitly sandbox or the runner records an `e2b_sandbox_run` model.
                        </div>
                        <div className="panel-muted p-4">
                            Use this page to validate cap behavior and to spot whether repo runs are more expensive than quick chat routing.
                        </div>
                    </div>
                </div>
            </section>

            <section className="table-shell">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Task mode</th>
                            <th>Models used</th>
                            <th className="text-right">Input tok</th>
                            <th className="text-right">Output tok</th>
                            <th className="text-right">Credits</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={6} className="px-5 py-8 text-center text-[var(--text-muted)]">
                                    Loading events...
                                </td>
                            </tr>
                        ) : events.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="px-5 py-8 text-center text-[var(--text-muted)]">
                                    No usage recorded in this time range.
                                </td>
                            </tr>
                        ) : (
                            events.map((event) => (
                                <tr key={event.id}>
                                    <td>
                                        <div className="inline-flex items-center gap-2">
                                            <Clock3 className="h-4 w-4 text-[var(--text-soft)]" />
                                            {new Date(event.created_at).toLocaleString(undefined, {
                                                month: "short",
                                                day: "numeric",
                                                hour: "numeric",
                                                minute: "2-digit",
                                            })}
                                        </div>
                                    </td>
                                    <td className="capitalize">{event.task_mode}</td>
                                    <td>
                                        <div className="flex flex-wrap gap-2">
                                            {event.models_used?.map((model: string) => (
                                                <span key={model} className="badge bg-slate-900/5 text-slate-700">
                                                    {model}
                                                </span>
                                            ))}
                                        </div>
                                    </td>
                                    <td className="text-right">{event.input_tokens?.toLocaleString?.() || 0}</td>
                                    <td className="text-right">{event.output_tokens?.toLocaleString?.() || 0}</td>
                                    <td className="text-right font-semibold text-[var(--accent-strong)]">{event.credits_consumed}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </section>
        </div>
    );
}
