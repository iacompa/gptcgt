"use client";

import { useCallback, useEffect, useState } from "react";
import { CreditCard, ShieldAlert, Trash2, UserRound } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { PricingTable } from "@/components/pricing-table";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { useToast } from "@/components/toaster";

export default function AccountPage() {
    const [profile, setProfile] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [capInput, setCapInput] = useState("");
    const [savingCap, setSavingCap] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const { pushToast } = useToast();

    const loadProfile = useCallback(async () => {
        try {
            const { data, error } = await apiClient.GET("/user/me");
            if (error) throw error;
            const nextProfile = data as any;
            setProfile(nextProfile);
            if (nextProfile?.spending_cap !== null && nextProfile?.spending_cap !== undefined) {
                setCapInput(nextProfile.spending_cap.toString());
            } else {
                setCapInput("");
            }
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Could not load account profile",
                description: error.message,
            });
        } finally {
            setLoading(false);
        }
    }, [pushToast]);

    useEffect(() => {
        void loadProfile();
    }, [loadProfile]);

    const updateCap = async () => {
        setSavingCap(true);
        try {
            const capValue = capInput === "" ? null : parseInt(capInput, 10);
            const { error } = await apiClient.PATCH("/user/me/spending_cap", {
                body: { spending_cap: capValue },
            });
            if (error) throw error;
            await loadProfile();
            pushToast({
                tone: "success",
                title: "Account cap saved",
                description: capValue === null ? "No monthly limit is set." : `Cap set to $${capValue}.`,
            });
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Failed to update account cap",
                description: error.message,
            });
        } finally {
            setSavingCap(false);
        }
    };

    const deleteAccount = async () => {
        setDeleting(true);
        try {
            const { error } = await apiClient.DELETE("/user/me");
            if (error) throw error;
            await fetch("/api/auth/signout", { method: "POST" });
            window.location.href = "/";
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Failed to delete account",
                description: error.message || "Please try again or contact support.",
            });
            setDeleting(false);
        }
    };

    if (loading) return <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">Loading account...</div>;
    if (!profile) return <div className="text-[var(--text-muted)]">Failed to load profile.</div>;

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <p className="eyebrow">Account</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                    Keep profile, billing, and destructive actions in one controlled place.
                </h1>
                <p className="mt-3 max-w-3xl copy-lg">
                    This page should make ownership clear: who you are, what plan you are on, and how hard limits or deletion behave.
                </p>
            </section>

            <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                <div className="space-y-6">
                    <div className="panel p-6">
                        <div className="flex items-center gap-2">
                            <UserRound className="h-5 w-5 text-[var(--accent)]" />
                            <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Profile</h2>
                        </div>
                        <div className="mt-5 grid gap-4">
                            <div>
                                <p className="metric-label">Email</p>
                                <div className="mt-2 rounded-[20px] border border-[var(--border)] bg-white/70 px-4 py-3 text-slate-900">
                                    {profile.email}
                                </div>
                            </div>
                            <div>
                                <p className="metric-label">Plan</p>
                                <div className="mt-2 rounded-[20px] border border-[var(--border)] bg-white/70 px-4 py-3 capitalize text-slate-900">
                                    {profile.plan}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="panel p-6">
                        <div className="flex items-center gap-2">
                            <ShieldAlert className="h-5 w-5 text-[var(--amber)]" />
                            <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Account spending cap</h2>
                        </div>
                        <p className="mt-3 text-sm text-[var(--text-muted)]">
                            Enforce a strict dollar limit on pay-as-you-go overage. Leave blank if you want no account-level cap.
                        </p>
                        <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end">
                            <div className="flex-1">
                                <label className="mb-2 block text-sm font-medium text-slate-900">Monthly limit ($)</label>
                                <input
                                    type="number"
                                    className="field"
                                    placeholder="No limit"
                                    value={capInput}
                                    onChange={(event) => setCapInput(event.target.value)}
                                />
                            </div>
                            <button type="button" onClick={updateCap} disabled={savingCap} className="btn-secondary">
                                {savingCap ? "Saving..." : "Save cap"}
                            </button>
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="panel p-6">
                        <div className="flex items-center gap-2">
                            <CreditCard className="h-5 w-5 text-[var(--accent)]" />
                            <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Plan options</h2>
                        </div>
                        <div className="mt-5">
                            <PricingTable currentPlan={profile.plan} />
                        </div>
                        <button
                            type="button"
                            className="btn-secondary mt-5"
                            onClick={async () => {
                                try {
                                    const { data, error } = await apiClient.POST("/billing/portal");
                                    if (error) throw error;
                                    if (data?.url) {
                                        window.location.href = data.url;
                                        return;
                                    }
                                    throw new Error("Billing portal URL was not returned.");
                                } catch (error: any) {
                                    pushToast({
                                        tone: "error",
                                        title: "Could not open billing portal",
                                        description: error.message,
                                    });
                                }
                            }}
                        >
                            Manage billing via Stripe
                        </button>
                    </div>

                    <div className="rounded-[28px] border border-red-200 bg-red-50 p-6">
                        <div className="flex items-center gap-2 text-red-800">
                            <Trash2 className="h-5 w-5" />
                            <h2 className="text-xl font-semibold tracking-[-0.03em]">Danger zone</h2>
                        </div>
                        <p className="mt-3 text-sm text-red-900/80">
                            Deleting the account cancels subscriptions, disables stored API keys, and anonymizes your identity. This cannot be undone.
                        </p>
                        <button type="button" onClick={() => setConfirmDelete(true)} className="btn-danger mt-5">
                            Delete account
                        </button>
                    </div>
                </div>
            </section>

            <ConfirmDialog
                open={confirmDelete}
                title="Delete account permanently?"
                description="This immediately cancels active subscriptions, disables API keys, and removes your identity from the product. This action cannot be undone."
                confirmLabel="Delete account"
                busy={deleting}
                onCancel={() => setConfirmDelete(false)}
                onConfirm={deleteAccount}
            />
        </div>
    );
}
