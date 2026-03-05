"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { CreditCard, ShieldAlert } from "lucide-react";

export default function BillingPage() {
    const [status, setStatus] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [teamSeats, setTeamSeats] = useState(5);
    const [creditAmount, setCreditAmount] = useState(500);

    useEffect(() => {
        loadStatus();
    }, []);

    const loadStatus = async () => {
        try {
            const { data, error } = await apiClient.GET("/billing/status");
            if (error) throw error;
            setStatus(data as any);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleCheckout = async (plan: string, quantity: number = 1) => {
        try {
            const { data, error } = await apiClient.POST("/billing/checkout", {
                body: { plan, annual: false, quantity } as any
            });
            if (error) throw error;
            if (data?.url) window.location.href = data.url;
        } catch (e) {
            alert("Checkout failed");
        }
    };

    const handlePortal = async () => {
        try {
            const { data, error } = await apiClient.POST("/billing/portal");
            if (error) throw error;
            if (data?.url) window.location.href = data.url;
        } catch (e) {
            alert("Portal access failed");
        }
    };

    const handlePurchaseCredits = async () => {
        try {
            const { data, error } = await apiClient.POST("/billing/credits", {
                body: { credit_amount: creditAmount } as any
            });
            if (error) throw error;
            if (data?.url) window.location.href = data.url;
        } catch (e) {
            alert("Failed to initiate credit purchase");
        }
    };

    const handleUpdateCap = async (e: React.FormEvent) => {
        e.preventDefault();
        const fd = new FormData(e.target as HTMLFormElement);
        const cap = fd.get("cap") ? parseInt(fd.get("cap") as string) : null;

        try {
            const { error } = await apiClient.PATCH("/user/me/spending_cap", {
                body: { spending_cap: cap }
            });
            if (error) throw error;
            loadStatus();
            alert("Spending cap updated");
        } catch (e) {
            alert("Failed to update cap");
        }
    }

    if (loading) return <div>Loading billing data...</div>;

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold">Billing & Usage</h1>
                <p className="text-gray-400 mt-1">Manage your active plans, credits, and spend limits.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {status?.billing_access ? (
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                        <h3 className="font-bold mb-4 flex items-center gap-2"><CreditCard /> Subscription Details</h3>
                        <div className="space-y-4">
                            <div className="flex justify-between border-b border-gray-800 pb-2">
                                <span className="text-gray-400">Company Plan</span>
                                <span className="font-medium capitalize">{status?.plan || "Free"} ({status?.subscription_status})</span>
                            </div>
                            <div className="flex justify-between border-b border-gray-800 pb-2">
                                <span className="text-gray-400">Team Wallet Remaining</span>
                                <span className="font-bold text-indigo-400">{status?.credits_remaining} <span className="text-sm font-normal text-gray-500">/ {status?.credits_monthly}</span></span>
                            </div>
                            {status?.current_period_end && (
                                <div className="flex justify-between border-b border-gray-800 pb-2">
                                    <span className="text-gray-400">Renews On</span>
                                    <span>{new Date(status.current_period_end).toLocaleDateString()}</span>
                                </div>
                            )}
                        </div>
                        <div className="mt-6 flex gap-4">
                            {status?.subscription_status === "active" ? (
                                <button onClick={handlePortal} className="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded text-sm font-medium w-full text-center">
                                    Manage Subscription
                                </button>
                            ) : (
                                <div className="space-y-4 w-full">
                                    <button onClick={() => handleCheckout("pro", 1)} className="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded text-sm font-medium w-full text-center">
                                        Upgrade to Pro ($29/mo)
                                    </button>

                                    <div className="p-4 border border-gray-800 rounded-lg bg-gray-900 shadow-inner">
                                        <h4 className="font-bold text-sm mb-3">Team Workspace</h4>
                                        <div className="flex items-center justify-between mb-4">
                                            <span className="text-sm text-gray-400">Seats ($49/user/mo)</span>
                                            <input
                                                type="number"
                                                min="1"
                                                max="100"
                                                value={teamSeats}
                                                onChange={(e) => setTeamSeats(Math.max(1, parseInt(e.target.value) || 1))}
                                                className="w-20 bg-gray-950 border border-gray-700 rounded px-3 py-1 text-sm text-center focus:outline-none focus:border-indigo-500"
                                            />
                                        </div>
                                        <button onClick={() => handleCheckout("team", teamSeats)} className="bg-gray-800 border border-gray-700 hover:bg-gray-700 px-4 py-2 rounded text-sm font-medium w-full text-center">
                                            Upgrade to Team (${49 * teamSeats}/mo)
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                        <h3 className="font-bold mb-4 flex items-center gap-2"><CreditCard /> My Engineering Quota</h3>
                        <p className="text-sm text-gray-400 mb-6">You are a Member of an Enterprise Workspace. Your Team Manager assigns your credit limits.</p>
                        <div className="space-y-4">
                            <div className="flex justify-between border-b border-gray-800 pb-2">
                                <span className="text-gray-400">My Monthly Quota</span>
                                <span className="font-medium">{status?.allocated_quota ? status.allocated_quota.toLocaleString() : "Unlimited (Using Team Wallet)"}</span>
                            </div>
                        </div>
                    </div>
                )}

                {status?.billing_access && (
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                        <h3 className="font-bold mb-4 flex items-center gap-2 text-amber-500"><ShieldAlert /> Spending Caps</h3>
                        <p className="text-sm text-gray-400 mb-6">Set a hard limit on monthly metered overage. The proxy will block all API requests once reached.</p>

                        <form onSubmit={handleUpdateCap} className="space-y-4 mb-8">
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">Monthly Limit ($)</label>
                                <div className="relative">
                                    <span className="absolute left-3 top-2.5 text-gray-500">$</span>
                                    <input
                                        type="number"
                                        name="cap"
                                        defaultValue={status?.spending_cap || ""}
                                        placeholder="No limit"
                                        className="w-full bg-gray-950 border border-gray-700 rounded-md py-2 pl-8 pr-4 text-white focus:outline-none focus:border-amber-500"
                                    />
                                </div>
                            </div>
                            <button type="submit" className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white px-4 py-2 rounded text-sm font-medium w-full">
                                Save Limit
                            </button>
                        </form>

                        <div className="pt-6 border-t border-gray-800">
                            <h3 className="font-bold mb-4 flex items-center gap-2 text-emerald-400"><CreditCard /> Top-Up Team Wallet</h3>
                            <p className="text-sm text-gray-400 mb-4">Pay-as-you-go credits for immediate use by your entire Team Workspace. Credits never expire.</p>

                            <div className="bg-gray-950 border border-gray-800 rounded-lg p-4 mb-4">
                                <div className="flex justify-between items-center mb-6">
                                    <span className="text-2xl font-bold text-white">{creditAmount.toLocaleString()} <span className="text-sm text-gray-500 font-normal">Credits</span></span>
                                    <span className="text-xl text-emerald-400 font-medium">${(creditAmount * 0.01).toFixed(2)}</span>
                                </div>

                                <input
                                    type="range"
                                    min="100"
                                    max="50000"
                                    step="100"
                                    value={creditAmount}
                                    onChange={(e) => setCreditAmount(parseInt(e.target.value))}
                                    className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                                />
                                <div className="flex justify-between text-xs text-gray-500 mt-2">
                                    <span>100</span>
                                    <span>50,000</span>
                                </div>
                            </div>

                            <button onClick={handlePurchaseCredits} className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-3 rounded-lg text-sm font-bold w-full shadow-lg shadow-emerald-900/20 transition-all">
                                Purchase {creditAmount.toLocaleString()} Credits for Team
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
