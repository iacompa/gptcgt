import Link from "next/link";
import { ArrowRight, Coins, GitBranch, ShieldCheck, Sparkles } from "lucide-react";
import { ProductPreview } from "@/components/product-preview";

export default function Home() {
    return (
        <div className="page-shell page-stack">
            <section className="grid gap-10 pb-8 pt-4 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
                <div className="space-y-7">
                    <div className="space-y-4">
                        <p className="eyebrow">Productive orchestration</p>
                        <h1 className="display-title">
                            Make the web app feel as sharp as the terminal.
                        </h1>
                        <p className="copy-lg max-w-2xl">
                            Route multiple models across the same repo, track the cost before you commit, and keep proof artifacts attached to every higher-risk change.
                        </p>
                    </div>

                    <div className="flex flex-col gap-3 sm:flex-row">
                        <Link href="/dashboard" className="btn-primary">
                            Open workspace <ArrowRight className="h-4 w-4" />
                        </Link>
                        <Link href="/pricing" className="btn-secondary">
                            Compare plans
                        </Link>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-3">
                        <div className="panel-muted p-4">
                            <p className="metric-label">Routing</p>
                            <p className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">Multi-model</p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">Compare cost, latency, and proof score before choosing.</p>
                        </div>
                        <div className="panel-muted p-4">
                            <p className="metric-label">Proof</p>
                            <p className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">Attached</p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">Guardrails, diffs, and checks stay close to the run.</p>
                        </div>
                        <div className="panel-muted p-4">
                            <p className="metric-label">Spend</p>
                            <p className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">Visible</p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">Caps and ledger views built into the workflow.</p>
                        </div>
                    </div>
                </div>
                <ProductPreview />
            </section>

            <section className="grid gap-4 lg:grid-cols-3">
                <div className="panel p-6">
                    <div className="badge badge-accent">
                        <GitBranch className="h-3.5 w-3.5" /> Hub
                    </div>
                    <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                        Browse repos, queue runs, and inspect logs without leaving the browser.
                    </h2>
                    <p className="mt-3 copy-sm">
                        The Hub is where GitHub connection, workspace context, run logs, and PR creation finally belong together.
                    </p>
                </div>
                <div className="panel p-6">
                    <div className="badge badge-amber">
                        <Coins className="h-3.5 w-3.5" /> Billing
                    </div>
                    <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                        Spend controls should be legible, not hidden behind settings pages.
                    </h2>
                    <p className="mt-3 copy-sm">
                        Team wallet state, renewals, top-ups, caps, and usage trends live in one connected workspace.
                    </p>
                </div>
                <div className="panel p-6">
                    <div className="badge bg-slate-900/5 text-slate-700">
                        <ShieldCheck className="h-3.5 w-3.5" /> Safety
                    </div>
                    <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                        Automation should feel controlled, reversible, and transparent.
                    </h2>
                    <p className="mt-3 copy-sm">
                        Proof checks, repo previews, billing signals, and explicit confirmation paths reduce the “black box” feeling.
                    </p>
                </div>
            </section>

            <section className="panel grid gap-8 p-6 sm:p-8 lg:grid-cols-[0.85fr_1.15fr]">
                <div>
                    <p className="eyebrow">Workflow</p>
                    <h2 className="section-title mt-3">A better UI means fewer mental context switches.</h2>
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                    <div className="panel-muted p-5">
                        <Sparkles className="h-5 w-5 text-[var(--accent)]" />
                        <h3 className="mt-4 text-lg font-semibold text-slate-950">Start with intent</h3>
                        <p className="mt-2 copy-sm">Prompt, model, repo, and spend information belong in the same decision surface.</p>
                    </div>
                    <div className="panel-muted p-5">
                        <GitBranch className="h-5 w-5 text-[var(--amber)]" />
                        <h3 className="mt-4 text-lg font-semibold text-slate-950">Stay in context</h3>
                        <p className="mt-2 copy-sm">Logs, file tree, and PR state should be visible without modal jumps or browser prompts.</p>
                    </div>
                    <div className="panel-muted p-5">
                        <ShieldCheck className="h-5 w-5 text-slate-900" />
                        <h3 className="mt-4 text-lg font-semibold text-slate-950">Finish with confidence</h3>
                        <p className="mt-2 copy-sm">Proof artifacts and billing outcomes need to be obvious before a user takes the last irreversible action.</p>
                    </div>
                </div>
            </section>
        </div>
    );
}
