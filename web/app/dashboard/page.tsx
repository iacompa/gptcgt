import { getServerApiClient } from "@/lib/api-server";
import { getSession } from "@/lib/auth";
import { ArrowRight, AlertTriangle, CreditCard, ShieldCheck, Sparkles, Wallet } from "lucide-react";
import Link from "next/link";

export const dynamic = 'force-dynamic';

export default async function DashboardOverview() {
    const session = await getSession();

    // Fetch user profile from the FastAPI backend
    let profile = null;
    let apiError = null;

    try {
        const client = await getServerApiClient();
        const { data, error } = await client.GET("/user/me");
        if (error) {
            apiError = "Failed to load profile details";
        } else {
            profile = data as any;
        }
    } catch (e: any) {
        apiError = e.message;
    }

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <p className="eyebrow">Workspace overview</p>
                <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <h1 className="text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                            Welcome back, {session?.user.name || "there"}.
                        </h1>
                        <p className="mt-3 max-w-2xl copy-lg">
                            Balance, plan state, and next actions are visible here before you jump into chat or a repo run.
                        </p>
                    </div>
                    <div className="rounded-full bg-white/70 px-4 py-2 text-sm text-[var(--text-muted)]">
                        {session?.user.email}
                    </div>
                </div>
            </section>

            {apiError && (
                <div className="rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-4 text-amber-900">
                    <p className="flex items-center gap-2 text-sm font-medium">
                        <AlertTriangle className="h-4 w-4" /> API connection issue
                    </p>
                    <p className="mt-1 text-sm opacity-80">{apiError}</p>
                    <p className="mt-1 text-sm opacity-70">Some data may be unavailable. Your session is still active.</p>
                </div>
            )}

            <section className="grid gap-4 md:grid-cols-3">
                <div className="metric-card">
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="metric-label">Credits remaining</p>
                            <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                                {profile?.credits_remaining ?? "—"}
                            </p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">
                                of {profile?.credits_monthly ?? "—"} this cycle
                            </p>
                        </div>
                        <CreditCard className="h-5 w-5 text-[var(--accent)]" />
                    </div>
                </div>
                <div className="metric-card">
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="metric-label">Current plan</p>
                            <p className="mt-3 text-3xl font-semibold capitalize tracking-[-0.04em] text-slate-950">
                                {profile?.plan || "Free"}
                            </p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">
                                Billing and access behavior follow this tier.
                            </p>
                        </div>
                        <Sparkles className="h-5 w-5 text-[var(--amber)]" />
                    </div>
                </div>
                <div className="metric-card">
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="metric-label">Hard spending cap</p>
                            <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                                {profile?.spending_cap ? `$${profile.spending_cap}` : "None"}
                            </p>
                            <p className="mt-1 text-sm text-[var(--text-muted)]">
                                Overage stops automatically at this threshold.
                            </p>
                        </div>
                        <Wallet className="h-5 w-5 text-slate-900" />
                    </div>
                </div>
            </section>

            <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="panel p-6">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Quick actions</h2>
                        <span className="badge badge-accent">Workspace</span>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        <Link href="/dashboard/chat" className="panel-muted p-4 transition hover:bg-white/80">
                            <p className="text-base font-semibold text-slate-950">Open chat</p>
                            <p className="mt-2 text-sm text-[var(--text-muted)]">
                                Route a prompt through the proxy and compare model behavior.
                            </p>
                            <span className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[var(--accent)]">
                                Start now <ArrowRight className="h-4 w-4" />
                            </span>
                        </Link>
                        <Link href="/dashboard/hub" className="panel-muted p-4 transition hover:bg-white/80">
                            <p className="text-base font-semibold text-slate-950">Launch a repo run</p>
                            <p className="mt-2 text-sm text-[var(--text-muted)]">
                                Connect GitHub, inspect files, and queue a guided automation run.
                            </p>
                            <span className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[var(--accent)]">
                                Open Hub <ArrowRight className="h-4 w-4" />
                            </span>
                        </Link>
                        <Link href="/dashboard/billing" className="panel-muted p-4 transition hover:bg-white/80">
                            <p className="text-base font-semibold text-slate-950">Review billing</p>
                            <p className="mt-2 text-sm text-[var(--text-muted)]">
                                Update plans, top up credits, and adjust caps without leaving the workspace.
                            </p>
                            <span className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[var(--accent)]">
                                Go to billing <ArrowRight className="h-4 w-4" />
                            </span>
                        </Link>
                        <Link href="/dashboard/team" className="panel-muted p-4 transition hover:bg-white/80">
                            <p className="text-base font-semibold text-slate-950">Manage team</p>
                            <p className="mt-2 text-sm text-[var(--text-muted)]">
                                Invite members, review roles, and keep shared usage organized.
                            </p>
                            <span className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[var(--accent)]">
                                Open team view <ArrowRight className="h-4 w-4" />
                            </span>
                        </Link>
                    </div>
                </div>

                <div className="panel p-6">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Recommended flow</h2>
                        <ShieldCheck className="h-5 w-5 text-[var(--amber)]" />
                    </div>
                    <div className="mt-5 space-y-4">
                        <div className="flex items-start gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent-strong)]">1</div>
                            <div>
                                <p className="text-sm font-medium text-slate-950">Connect keys or use managed credits</p>
                                <p className="mt-1 text-sm text-[var(--text-muted)]">
                                    Start with BYOK, or route through the managed proxy if you want one bill.
                                </p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent-strong)]">2</div>
                            <div>
                                <p className="text-sm font-medium text-slate-950">Use chat for fast probing</p>
                                <p className="mt-1 text-sm text-[var(--text-muted)]">
                                    Compare model behavior before escalating to a repo-aware run.
                                </p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent-strong)]">3</div>
                            <div>
                                <p className="text-sm font-medium text-slate-950">Launch Hub for repo work</p>
                                <p className="mt-1 text-sm text-[var(--text-muted)]">
                                    Move to Hub only when you need diffs, proof, PR output, or log visibility.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
