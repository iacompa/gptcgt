"use client";

import { useState, useEffect } from "react";
import { fetchAPI } from "@/lib/api";
import { PricingTable } from "@/components/pricing-table";

export default function AccountPage() {
    const [profile, setProfile] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [capInput, setCapInput] = useState("");
    const [savingCap, setSavingCap] = useState(false);

    useEffect(() => {
        loadProfile();
    }, []);

    const loadProfile = async () => {
        try {
            const data = await fetchAPI("/user/me");
            setProfile(data);
            if (data.spending_cap !== null) {
                setCapInput(data.spending_cap.toString());
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const updateCap = async () => {
        setSavingCap(true);
        try {
            const capVal = capInput === "" ? null : parseInt(capInput);
            await fetchAPI("/user/me/spending_cap", {
                method: "PATCH",
                body: JSON.stringify({ spending_cap: capVal })
            });
            loadProfile();
        } catch (e) {
            console.error(e);
            alert("Failed to update spending cap");
        } finally {
            setSavingCap(false);
        }
    };

    if (loading) return <div>Loading account...</div>;
    if (!profile) return <div>Failed to load profile.</div>;

    return (
        <div className="max-w-4xl">
            <h1 className="text-2xl font-bold mb-6">Account Settings</h1>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
                <h2 className="text-lg font-bold mb-4">Profile Information</h2>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Email</label>
                        <div className="text-white bg-gray-950 px-4 py-2 rounded border border-gray-800">{profile.email}</div>
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Plan</label>
                        <div className="text-white bg-gray-950 px-4 py-2 rounded border border-gray-800 capitalize">{profile.plan}</div>
                    </div>
                </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
                <h2 className="text-lg font-bold mb-4">Hard Spending Cap</h2>
                <p className="text-gray-400 text-sm mb-4">Enforce a strict dollar limit on Pay-As-You-Go overage per month. Leave blank for no cap.</p>

                <div className="flex gap-4 items-end">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Monthly Limit ($)</label>
                        <input
                            type="number"
                            className="bg-gray-950 border border-gray-700 rounded-md px-4 py-2 text-white focus:outline-none focus:border-indigo-500 w-48"
                            placeholder="No Limit"
                            value={capInput}
                            onChange={(e) => setCapInput(e.target.value)}
                        />
                    </div>
                    <button
                        onClick={updateCap}
                        disabled={savingCap}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-md font-medium disabled:opacity-50"
                    >
                        {savingCap ? "Saving..." : "Save Cap"}
                    </button>
                </div>
            </div>

            <div className="mb-8">
                <h2 className="text-lg font-bold mb-4">Plan & Billing</h2>
                <PricingTable currentPlan={profile.plan} />

                <div className="mt-4 flex justify-end">
                    <button
                        className="text-indigo-400 hover:text-indigo-300 text-sm font-medium"
                        onClick={async () => {
                            try {
                                const res = await fetchAPI("/billing/portal", { method: "POST" });
                                if (res?.url) window.location.href = res.url;
                            } catch (e) {
                                alert("Could not open billing portal. Please try again.");
                            }
                        }}
                    >
                        Manage Billing via Stripe &rarr;
                    </button>
                </div>
            </div>

            <div className="bg-red-950/20 border border-red-900/50 rounded-xl p-6">
                <h2 className="text-lg font-bold text-red-500 mb-2">Danger Zone</h2>
                <p className="text-gray-400 text-sm mb-4">Permanently delete your account and all associated data. This action cannot be undone.</p>
                <button className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-md font-medium text-sm">
                    Delete Account
                </button>
            </div>

        </div>
    );
}
