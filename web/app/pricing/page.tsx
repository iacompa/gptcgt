"use client";

import { Check, Shield, Database, Users, KeyRound, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/toaster";

export default function PricingPage() {
    const [loadingPack, setLoadingPack] = useState<number | null>(null);
    const { pushToast } = useToast();

    const handleBuyPack = async (amount: number) => {
        try {
            setLoadingPack(amount);
            const { data, error } = await apiClient.POST("/billing/credits", {
                body: { credit_amount: amount } as any
            });
            if (error) throw error;
            if (data?.url) {
                window.location.href = data.url;
            } else {
                pushToast({
                    tone: "error",
                    title: "Could not open checkout",
                    description: "The billing service did not return a checkout URL.",
                });
            }
        } catch (e: any) {
            if (e.message && e.message.includes("Authorization")) {
                window.location.href = "/auth?redirect_url=/pricing";
            } else {
                pushToast({
                    tone: "error",
                    title: "Credit pack checkout failed",
                    description: e.message,
                });
            }
        } finally {
            setLoadingPack(null);
        }
    };

    return (
        <div className="page-shell page-stack">
            <div className="hero-panel px-6 py-10 text-center sm:px-10">
                <p className="eyebrow">Pricing</p>
                <p className="mt-3 text-4xl font-semibold tracking-[-0.05em] text-slate-950 sm:text-5xl">
                    Scale capability, not dashboard chaos.
                </p>
                <p className="mx-auto mt-4 max-w-3xl copy-lg">
                    Use your own keys for the CLI, or subscribe for managed credits that unlock the web workspace, shared billing controls, and faster onboarding for teams.
                </p>
            </div>

            <div className="grid gap-6 lg:grid-cols-4">
                {/* BYOK Free Tier */}
                <div className="panel flex flex-col justify-between p-8">
                    <div>
                        <div className="flex items-center gap-2">
                            <KeyRound className="h-5 w-5 text-[var(--accent)]" />
                            <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">BYOK (CLI)</h3>
                        </div>
                        <p className="mt-4 copy-sm">Bring your own keys. Use your own API accounts locally in the CLI and pay providers directly.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-semibold tracking-[-0.03em] text-[var(--accent)]">Free</span>
                            <span className="text-sm font-semibold leading-6 text-[var(--text-soft)]">forever</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-[var(--text-muted)]">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> All 6 operation modes</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Unlimited usage</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> 10+ provider integrations</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Local model support</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> OS keychain storage</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> ELO routing and comparisons</li>
                        </ul>
                    </div>
                    <Link href="/docs/keys" className="btn-secondary mt-8">
                        Get started — it&apos;s free
                    </Link>
                </div>

                {/* Pro Plan */}
                <div className="panel flex flex-col justify-between p-8">
                    <div>
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">Pro</h3>
                        <p className="mt-4 copy-sm">Managed credits and zero-config access across providers for a single developer.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-semibold tracking-[-0.03em] text-slate-950">$29</span>
                            <span className="text-sm font-semibold leading-6 text-[var(--text-soft)]">/month</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-[var(--text-muted)]">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> 1,000 credits monthly</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Optional pay-as-you-go overage</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> No provider keys required</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Standard support</li>
                        </ul>
                    </div>
                    <Link href="/dashboard/billing" className="btn-secondary mt-8">
                        Get started
                    </Link>
                </div>

                {/* Team Plan */}
                <div className="hero-panel relative flex flex-col justify-between p-8">
                    <div className="badge badge-accent absolute right-6 top-0 -translate-y-1/2">Most popular</div>
                    <div>
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">Team</h3>
                        <p className="mt-4 copy-sm">For engineering groups that need shared wallet controls, safer automation, and one billing surface.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-semibold tracking-[-0.03em] text-slate-950">$49</span>
                            <span className="text-sm font-semibold leading-6 text-[var(--text-soft)]">/seat/month</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-[var(--text-muted)]">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> 2,000 credits monthly per seat</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Hard spending caps</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Shared organization keys</li>
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Priority support</li>
                        </ul>
                    </div>
                    <Link href="/dashboard/billing" className="btn-primary mt-8">
                        Start Team Trial
                    </Link>
                </div>

                {/* Enterprise Plan */}
                <div className="panel flex flex-col justify-between p-8">
                    <div>
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">Enterprise</h3>
                        <p className="mt-4 copy-sm">Advanced security, governance, and organizational workflow support for larger teams.</p>
                        <p className="mt-6 flex items-baseline gap-x-1">
                            <span className="text-4xl font-semibold tracking-[-0.03em] text-slate-950">$149</span>
                            <span className="text-sm font-semibold leading-6 text-[var(--text-soft)]">/seat/month</span>
                        </p>
                        <ul className="mt-8 space-y-3 text-sm leading-6 text-[var(--text-muted)]">
                            <li className="flex gap-x-3"><Check className="h-6 w-5 flex-none text-[var(--accent)]" /> Custom credit volumes</li>
                            <li className="flex gap-x-3"><Shield className="h-6 w-5 flex-none text-[var(--accent)]" /> Compliance and audit support</li>
                            <li className="flex gap-x-3"><Users className="h-6 w-5 flex-none text-[var(--accent)]" /> SAML SSO via WorkOS</li>
                            <li className="flex gap-x-3"><Database className="h-6 w-5 flex-none text-[var(--accent)]" /> Data residency guarantees</li>
                        </ul>
                    </div>
                    <Link href="mailto:sales@ia-compa.com" className="btn-secondary mt-8">
                        Contact Sales
                    </Link>
                </div>
            </div>

            <div className="panel px-6 py-8 text-center sm:px-8">
                <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">Pay-as-you-go credit packs</h3>
                <p className="mx-auto mt-3 max-w-3xl copy-sm">
                    Need extra capacity this month? Purchase non-expiring proxy credits for burst work, demos, or one-off migrations.
                </p>

                <div className="mt-8 grid gap-6 md:grid-cols-3">
                    <div className="panel-muted p-6">
                        <div className="text-xl font-semibold text-slate-950">100 Credits</div>
                        <div className="mt-2 inline-block rounded-full bg-white/80 px-3 py-1 text-sm text-[var(--text-muted)]">$1.00</div>
                        <button
                            onClick={() => handleBuyPack(100)}
                            disabled={loadingPack !== null}
                            className="btn-secondary mt-5 w-full"
                        >
                            {loadingPack === 100 ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                            Buy Pack
                        </button>
                    </div>
                    <div className="hero-panel relative p-6">
                        <div className="badge badge-accent absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2">Value</div>
                        <div className="text-xl font-semibold text-slate-950">500 Credits</div>
                        <div className="mt-2 inline-block rounded-full bg-white/80 px-3 py-1 text-sm text-[var(--text-muted)]">$5.00</div>
                        <button
                            onClick={() => handleBuyPack(500)}
                            disabled={loadingPack !== null}
                            className="btn-primary mt-5 w-full"
                        >
                            {loadingPack === 500 ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                            Buy Pack
                        </button>
                    </div>
                    <div className="panel-muted p-6">
                        <div className="text-xl font-semibold text-slate-950">1,000 Credits</div>
                        <div className="mt-2 inline-block rounded-full bg-white/80 px-3 py-1 text-sm text-[var(--text-muted)]">$10.00</div>
                        <button
                            onClick={() => handleBuyPack(1000)}
                            disabled={loadingPack !== null}
                            className="btn-secondary mt-5 w-full"
                        >
                            {loadingPack === 1000 ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                            Buy Pack
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
