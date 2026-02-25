"use client";

import { useState, useEffect } from "react";
import { fetchAPI } from "@/lib/api";
import { CreditCard, ShieldAlert } from "lucide-react";

export default function BillingPage() {
    const [status, setStatus] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStatus();
    }, []);

    const loadStatus = async () => {
        try {
            const data = await fetchAPI("/billing/status");
            setStatus(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleCheckout = async (plan: string) => {
        try {
            const data = await fetchAPI("/billing/checkout", {
                method: "POST",
                body: JSON.stringify({ plan, annual: false })
            });
            window.location.href = data.url;
        } catch (e) {
            alert("Checkout failed");
        }
    };

    const handlePortal = async () => {
        try {
            const data = await fetchAPI("/billing/portal", { method: "POST" });
            window.location.href = data.url;
        } catch (e) {
            alert("Portal access failed");
        }
    };

    const handleUpdateCap = async (e: React.FormEvent) => {
        e.preventDefault();
        const fd = new FormData(e.target as HTMLFormElement);
        const cap = fd.get("cap") ? parseInt(fd.get("cap") as string) : null;

        try {
            await fetchAPI("/user/me/spending_cap", {
                method: "PATCH",
                body: JSON.stringify({ spending_cap: cap })
            });
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
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="font-bold mb-4 flex items-center gap-2"><CreditCard /> Subscription Details</h3>
                    <div className="space-y-4">
                        <div className="flex justify-between border-b border-gray-800 pb-2">
                            <span className="text-gray-400">Current Plan</span>
                            <span className="font-medium capitalize">{status?.plan || "Free"} ({status?.subscription_status})</span>
                        </div>
                        <div className="flex justify-between border-b border-gray-800 pb-2">
                            <span className="text-gray-400">Credits Remaining</span>
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
                            <button onClick={() => handleCheckout("pro")} className="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded text-sm font-medium w-full text-center">
                                Upgrade to Pro
                            </button>
                        )}
                    </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="font-bold mb-4 flex items-center gap-2 text-amber-500"><ShieldAlert /> Spending Caps</h3>
                    <p className="text-sm text-gray-400 mb-6">Set a hard limit on monthly metered overage. The proxy will block all API requests once reached.</p>

                    <form onSubmit={handleUpdateCap} className="space-y-4">
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
                </div>
            </div>
        </div>
    );
}
