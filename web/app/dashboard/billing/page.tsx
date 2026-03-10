"use client";

import { useCallback, useEffect, useState } from "react";
import { CreditCard, ShieldAlert, Wallet } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/toaster";

export default function BillingPage() {
    const [status, setStatus] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [teamSeats, setTeamSeats] = useState(5);
    const [creditAmount, setCreditAmount] = useState(500);
    const [capInput, setCapInput] = useState("");
    const { pushToast } = useToast();

    const loadStatus = useCallback(async () => {
        try {
            const { data, error } = await apiClient.GET("/billing/status");
            if (error) throw error;
            const nextStatus = data as any;
            setStatus(nextStatus);
            setCapInput(nextStatus?.spending_cap ? String(nextStatus.spending_cap) : "");
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Could not load billing status",
                description: error.message,
            });
        } finally {
            setLoading(false);
        }
    }, [pushToast]);

    useEffect(() => {
        void loadStatus();
    }, [loadStatus]);

    const redirectToBillingUrl = async (task: () => Promise<any>, failureTitle: string) => {
        try {
            const { data, error } = await task();
            if (error) throw error;
            if (data?.url) {
                window.location.href = data.url;
                return;
            }
            throw new Error("The billing service did not return a redirect URL.");
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: failureTitle,
                description: error.message || "Please try again.",
            });
        }
    };

    const handleCheckout = async (plan: string, quantity: number = 1) => {
        await redirectToBillingUrl(
            () =>
                apiClient.POST("/billing/checkout", {
                    body: { plan, annual: false, quantity } as any,
                }),
            "Checkout failed"
        );
    };

    const handlePortal = async () => {
        await redirectToBillingUrl(() => apiClient.POST("/billing/portal"), "Portal access failed");
    };

    const handlePurchaseCredits = async () => {
        await redirectToBillingUrl(
            () =>
                apiClient.POST("/billing/credits", {
                    body: { credit_amount: creditAmount } as any,
                }),
            "Credit purchase failed"
        );
    };

    const handleUpdateCap = async (event: React.FormEvent) => {
        event.preventDefault();
        const value = capInput.trim() === "" ? null : parseInt(capInput, 10);
        try {
            const { error } = await apiClient.PATCH("/user/me/spending_cap", {
                body: { spending_cap: value },
            });
            if (error) throw error;
            await loadStatus();
            pushToast({
                tone: "success",
                title: "Spending cap updated",
                description: value === null ? "Monthly overage cap removed." : `Cap set to $${value}.`,
            });
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "Could not update spending cap",
                description: error.message,
            });
        }
    };

    if (loading) {
        return <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">Loading billing data...</div>;
    }

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <p className="eyebrow">Billing</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                    Manage plans, caps, and credit top-ups without leaving the workspace.
                </h1>
                <p className="mt-3 max-w-3xl copy-lg">
                    Subscription state, wallet balance, renewal timing, and overage controls should feel operational, not hidden.
                </p>
            </section>

            <section className="grid gap-4 md:grid-cols-3">
                <div className="metric-card">
                    <p className="metric-label">Plan</p>
                    <p className="mt-3 text-3xl font-semibold capitalize tracking-[-0.04em] text-slate-950">
                        {status?.plan || "Free"}
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">{status?.subscription_status || "inactive"}</p>
                </div>
                <div className="metric-card">
                    <p className="metric-label">Wallet balance</p>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                        {status?.credits_remaining?.toLocaleString?.() ?? status?.credits_remaining ?? "—"}
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">
                        of {status?.credits_monthly?.toLocaleString?.() ?? status?.credits_monthly ?? "—"} monthly credits
                    </p>
                </div>
                <div className="metric-card">
                    <p className="metric-label">Renewal</p>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                        {status?.current_period_end ? new Date(status.current_period_end).toLocaleDateString() : "N/A"}
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">Current billing cycle end</p>
                </div>
            </section>

            {status?.billing_access ? (
                <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
                    <div className="panel p-6">
                        <div className="flex items-center gap-2">
                            <CreditCard className="h-5 w-5 text-[var(--accent)]" />
                            <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Subscription controls</h2>
                        </div>
                        <div className="mt-5 grid gap-4 sm:grid-cols-2">
                            <div className="panel-muted p-5">
                                <p className="metric-label">Pro</p>
                                <p className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-slate-950">$29/mo</p>
                                <p className="mt-2 text-sm text-[var(--text-muted)]">Single-user managed credits with optional overage.</p>
                                <button type="button" onClick={() => handleCheckout("pro", 1)} className="btn-secondary mt-5 w-full">
                                    Choose Pro
                                </button>
                            </div>
                            <div className="hero-panel p-5">
                                <p className="metric-label">Team</p>
                                <p className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-slate-950">$49/seat/mo</p>
                                <p className="mt-2 text-sm text-[var(--text-muted)]">Shared wallet, org keys, and stronger control surfaces.</p>
                                <label className="mt-4 block text-sm font-medium text-slate-900">Seats</label>
                                <input
                                    type="number"
                                    min="1"
                                    max="100"
                                    value={teamSeats}
                                    onChange={(event) => setTeamSeats(Math.max(1, parseInt(event.target.value || "1", 10)))}
                                    className="field mt-2"
                                />
                                <button type="button" onClick={() => handleCheckout("team", teamSeats)} className="btn-primary mt-4 w-full">
                                    Start Team
                                </button>
                            </div>
                        </div>
                        <div className="soft-divider my-6" />
                        <button type="button" onClick={handlePortal} className="btn-secondary">
                            Manage subscription in Stripe
                        </button>
                    </div>

                    <div className="space-y-6">
                        <div className="panel p-6">
                            <div className="flex items-center gap-2">
                                <ShieldAlert className="h-5 w-5 text-[var(--amber)]" />
                                <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Monthly overage guardrail</h2>
                            </div>
                            <form onSubmit={handleUpdateCap} className="mt-5 space-y-4">
                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-900">Hard cap ($)</label>
                                    <input
                                        type="number"
                                        value={capInput}
                                        onChange={(event) => setCapInput(event.target.value)}
                                        placeholder="No limit"
                                        className="field"
                                    />
                                </div>
                                <p className="text-sm text-[var(--text-muted)]">
                                    Requests are blocked once metered overage reaches this number.
                                </p>
                                <button type="submit" className="btn-secondary">
                                    Save cap
                                </button>
                            </form>
                        </div>

                        <div className="panel p-6">
                            <div className="flex items-center gap-2">
                                <Wallet className="h-5 w-5 text-[var(--accent)]" />
                                <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Top up wallet</h2>
                            </div>
                            <p className="mt-3 text-sm text-[var(--text-muted)]">
                                Non-expiring credits for burst demand, shared immediately across the team workspace.
                            </p>
                            <div className="mt-5 rounded-[24px] border border-[var(--border)] bg-white/70 p-5">
                                <div className="flex items-end justify-between gap-4">
                                    <div>
                                        <p className="metric-label">Purchase size</p>
                                        <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                                            {creditAmount.toLocaleString()} credits
                                        </p>
                                    </div>
                                    <p className="text-2xl font-semibold tracking-[-0.03em] text-[var(--accent)]">
                                        ${(creditAmount * 0.01).toFixed(2)}
                                    </p>
                                </div>
                                <input
                                    type="range"
                                    min="100"
                                    max="50000"
                                    step="100"
                                    value={creditAmount}
                                    onChange={(event) => setCreditAmount(parseInt(event.target.value, 10))}
                                    className="mt-6 w-full accent-[var(--accent)]"
                                />
                                <div className="mt-2 flex justify-between text-xs text-[var(--text-soft)]">
                                    <span>100</span>
                                    <span>50,000</span>
                                </div>
                            </div>
                            <button type="button" onClick={handlePurchaseCredits} className="btn-primary mt-5 w-full">
                                Purchase credits
                            </button>
                        </div>
                    </div>
                </section>
            ) : (
                <section className="panel p-6">
                    <div className="flex items-center gap-2">
                        <Wallet className="h-5 w-5 text-[var(--accent)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Team-assigned quota</h2>
                    </div>
                    <p className="mt-3 max-w-2xl text-sm text-[var(--text-muted)]">
                        You are using a shared enterprise workspace. Your team admin controls the wallet and your quota allocation.
                    </p>
                    <div className="mt-5 rounded-[24px] border border-[var(--border)] bg-white/70 p-5">
                        <p className="metric-label">Allocated quota</p>
                        <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950">
                            {status?.allocated_quota ? status.allocated_quota.toLocaleString() : "Unlimited"}
                        </p>
                        <p className="mt-1 text-sm text-[var(--text-muted)]">Using the shared team wallet</p>
                    </div>
                </section>
            )}
        </div>
    );
}
