import { fetchAPI } from "@/lib/api-server";
import { Key, CreditCard, Activity, AlertTriangle } from "lucide-react";
import Link from "next/link";

export default async function DashboardOverview() {
    // Fetch user profile from the fastAPI backend
    let profile = null;
    let error = null;

    try {
        profile = await fetchAPI("/user/me");
    } catch (e: any) {
        error = e.message;
    }

    if (error) {
        return (
            <div className="p-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200">
                <p className="font-bold flex gap-2"><AlertTriangle /> Error loading overview</p>
                <p className="text-sm mt-1">{error}</p>
                <p className="text-xs text-gray-400 mt-2">Ensure the FastAPI backend is running on port 8000.</p>
            </div>
        );
    }

    return (
        <div>
            <h1 className="text-2xl font-bold mb-6">Overview</h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-gray-400 font-medium text-sm">Credits Remaining</h3>
                        <CreditCard className="text-indigo-400 h-5 w-5" />
                    </div>
                    <p className="text-3xl font-bold text-white">{profile?.credits_remaining || 0} <span className="text-sm text-gray-500 font-normal">/ {profile?.credits_monthly}</span></p>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-gray-400 font-medium text-sm">Current Plan</h3>
                        <Activity className="text-emerald-400 h-5 w-5" />
                    </div>
                    <p className="text-3xl font-bold text-white capitalize">{profile?.plan || "Free"} <span className="text-sm text-gray-500 font-normal">Tier</span></p>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-gray-400 font-medium text-sm">Spending Cap</h3>
                        <AlertTriangle className="text-amber-400 h-5 w-5" />
                    </div>
                    <p className="text-3xl font-bold text-white">{profile?.spending_cap ? `$${profile.spending_cap}` : "None"}</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-4">Recent Activity</h3>
                    <div className="text-gray-400 text-sm py-8 text-center border-2 border-dashed border-gray-800 rounded-lg">
                        No recent activity detected. Connect an agent to begin.
                    </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-4">Quick Links</h3>
                    <div className="space-y-3">
                        <Link href="/dashboard/keys" className="flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 transition">
                            <span className="flex items-center gap-3 text-sm font-medium"><Key size={16} /> Manage API Keys</span>
                            <span className="text-gray-400 text-xs">→</span>
                        </Link>
                        <Link href="/dashboard/billing" className="flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 transition">
                            <span className="flex items-center gap-3 text-sm font-medium"><CreditCard size={16} /> Manage Subscription</span>
                            <span className="text-gray-400 text-xs">→</span>
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
