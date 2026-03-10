"use client";

import { Check } from "lucide-react";

export function PricingTable({
    onSelectPlan,
    currentPlan,
}: {
    onSelectPlan?: (plan: string) => void;
    currentPlan?: string;
}) {
    const plans = [
        {
            name: "free",
            label: "Free (BYOK)",
            price: "$0",
            features: ["Bring your own keys", "Local orchestration", "CLI-first usage"],
        },
        {
            name: "pro",
            label: "Pro",
            price: "$29/mo",
            features: ["1,000 managed credits", "Optional overage", "Single-user workspace"],
        },
        {
            name: "team",
            label: "Team",
            price: "$49/user/mo",
            features: ["2,000 credits per seat", "Shared wallet", "Stronger controls"],
        },
    ];

    return (
        <div className="grid gap-4 md:grid-cols-3">
            {plans.map((plan) => {
                const isCurrent = currentPlan === plan.name;
                return (
                    <div key={plan.name} className={isCurrent ? "hero-panel p-5" : "panel-muted p-5"}>
                        <div className="flex items-center justify-between gap-3">
                            <h3 className="text-lg font-semibold tracking-[-0.03em] text-slate-950">{plan.label}</h3>
                            {isCurrent && <span className="badge badge-accent">Current</span>}
                        </div>
                        <p className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-slate-950">{plan.price}</p>
                        <ul className="mt-5 space-y-3 text-sm text-[var(--text-muted)]">
                            {plan.features.map((feature) => (
                                <li key={feature} className="flex gap-2">
                                    <Check className="mt-0.5 h-4 w-4 flex-none text-[var(--accent)]" />
                                    {feature}
                                </li>
                            ))}
                        </ul>
                        {onSelectPlan && !isCurrent && (
                            <button
                                type="button"
                                onClick={() => onSelectPlan(plan.name)}
                                className="btn-secondary mt-6 w-full"
                            >
                                Select {plan.label}
                            </button>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
