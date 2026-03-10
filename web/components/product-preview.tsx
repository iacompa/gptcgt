import { ArrowRight, BadgeCheck, Bot, GitBranch, Layers3, ShieldCheck } from "lucide-react";

export function ProductPreview() {
    return (
        <div className="hero-panel overflow-hidden p-6 sm:p-8">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-5">
                <div>
                    <p className="eyebrow">Live Workspace</p>
                    <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">
                        One cockpit for routing, proof, and spend control
                    </h3>
                </div>
                <span className="badge badge-accent">
                    <BadgeCheck className="h-3.5 w-3.5" /> Verified path
                </span>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                <div className="terminal-shell overflow-hidden">
                    <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 text-xs text-slate-400">
                        <span className="mono">runner / antigravity-agent</span>
                        <span className="badge bg-white/5 text-emerald-300">active</span>
                    </div>
                    <div className="space-y-3 px-4 py-4 text-sm text-slate-300">
                        <div className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3">
                            <div className="flex items-center gap-3">
                                <GitBranch className="h-4 w-4 text-emerald-300" />
                                <span>Repository cloned and indexed</span>
                            </div>
                            <span className="mono text-xs text-slate-500">00:04</span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3">
                            <div className="flex items-center gap-3">
                                <Bot className="h-4 w-4 text-sky-300" />
                                <span>Three-model routing pass with diff scoring</span>
                            </div>
                            <span className="mono text-xs text-slate-500">00:12</span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3">
                            <div className="flex items-center gap-3">
                                <ShieldCheck className="h-4 w-4 text-amber-300" />
                                <span>Proof bundle validated before PR creation</span>
                            </div>
                            <span className="mono text-xs text-slate-500">00:19</span>
                        </div>
                        <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-emerald-100">
                            <div className="flex items-center justify-between">
                                <span className="font-medium">PR ready for review</span>
                                <ArrowRight className="h-4 w-4" />
                            </div>
                            <p className="mt-2 text-xs text-emerald-100/80">
                                2 files changed, 1 proof artifact attached, estimated cost $0.41
                            </p>
                        </div>
                    </div>
                </div>

                <div className="space-y-4">
                    <div className="panel-muted p-5">
                        <p className="metric-label">Route Strategy</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                            <span className="badge badge-accent">Scout</span>
                            <span className="badge bg-slate-900/5 text-slate-700">Standard</span>
                            <span className="badge badge-amber">Verifier</span>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
                            Route fast questions to cheap models, escalate only when the proof score or repo complexity warrants it.
                        </p>
                    </div>
                    <div className="panel-muted p-5">
                        <p className="metric-label">Controls</p>
                        <div className="mt-3 grid gap-3">
                            <div className="rounded-2xl bg-white/70 px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                                    <Layers3 className="h-4 w-4 text-[var(--accent)]" />
                                    Hard monthly cap
                                </div>
                                <p className="mt-1 text-sm text-[var(--text-muted)]">$220 team guardrail</p>
                            </div>
                            <div className="rounded-2xl bg-white/70 px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                                    <ShieldCheck className="h-4 w-4 text-[var(--amber)]" />
                                    Safety gate
                                </div>
                                <p className="mt-1 text-sm text-[var(--text-muted)]">Proof, policy, and PR checks before merge</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
