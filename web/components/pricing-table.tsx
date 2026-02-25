"use client";

import { Check } from "lucide-react";

export function PricingTable({
    onSelectPlan,
    currentPlan
}: {
    onSelectPlan?: (plan: string) => void;
    currentPlan?: string;
}) {
    const plans = [
        {
            name: "free",
            label: "Free (BYOK)",
            price: "$0",
            features: ["Bring your own keys", "Basic orchestration", "Community support"]
        },
        {
            name: "pro",
            label: "Pro",
            price: "$29/mo",
            features: ["1,000 requests/mo", "Proxy hard caps", "Standard support"]
        },
        {
            name: "team",
            label: "Team",
            price: "$49/user/mo",
            features: ["2,000 requests/mo/user", "Shared API keys", "Priority support"]
        }
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map(p => (
                <div key={p.name} className={`bg-gray-900 border ${currentPlan === p.name ? 'border-indigo-500' : 'border-gray-800'} rounded-xl p-6 relative`}>
                    {currentPlan === p.name && (
                        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-indigo-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                            Current Plan
                        </div>
                    )}
                    <h3 className="font-bold text-lg">{p.label}</h3>
                    <div className="text-2xl font-bold my-4">{p.price}</div>
                    <ul className="space-y-2 mb-6 text-sm text-gray-400">
                        {p.features.map(f => (
                            <li key={f} className="flex gap-2"><Check size={16} className="text-indigo-400 shrink-0" /> {f}</li>
                        ))}
                    </ul>
                    {onSelectPlan && currentPlan !== p.name && (
                        <button
                            onClick={() => onSelectPlan(p.name)}
                            className="w-full bg-gray-800 hover:bg-gray-700 text-white rounded py-2 text-sm transition"
                        >
                            Select {p.label}
                        </button>
                    )}
                </div>
            ))}
        </div>
    );
}
