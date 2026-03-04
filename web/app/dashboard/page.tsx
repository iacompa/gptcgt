import { fetchAPI } from "@/lib/api-server";
import { getSession } from "@/lib/auth";
import { Key, CreditCard, Activity, AlertTriangle, Zap, Users } from "lucide-react";
import Link from "next/link";

export const dynamic = 'force-dynamic';

export default async function DashboardOverview() {
    const session = await getSession();

    // Fetch user profile from the FastAPI backend
    let profile = null;
    let apiError = null;

    try {
        profile = await fetchAPI("/user/me");
    } catch (e: any) {
        apiError = e.message;
    }

    return (
        <div>
            <h1 className="text-2xl font-bold mb-2">Welcome back, {session?.user.name || "there"} 👋</h1>
            <p className="text-gray-400 mb-6 text-sm">{session?.user.email}</p>

            {apiError && (
                <div className="p-4 bg-amber-900/20 border border-amber-600/30 rounded-lg text-amber-200 mb-6">
                    <p className="font-medium flex items-center gap-2 text-sm"><AlertTriangle className="w-4 h-4" /> API connection issue</p>
                    <p className="text-xs text-amber-300/70 mt-1">{apiError}</p>
                    <p className="text-xs text-gray-400 mt-1">Some data may be unavailable. Your session is active.</p>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-gray-400 font-medium text-sm">Credits Remaining</h3>
                        <CreditCard className="text-indigo-400 h-5 w-5" />
                    </div>
                    <p className="text-3xl font-bold text-white">
                        {profile?.credits_remaining ?? "—"}{" "}
                        <span className="text-sm text-gray-500 font-normal">/ {profile?.credits_monthly ?? "—"}</span>
                    </p>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-gray-400 font-medium text-sm">Current Plan</h3>
                        <Zap className="text-emerald-400 h-5 w-5" />
                    </div>
                    <p className="text-3xl font-bold text-white capitalize">
                        {profile?.plan || "Free"}{" "}
                        <span className="text-sm text-gray-500 font-normal">Tier</span>
                    </p>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-gray-400 font-medium text-sm">Spending Cap</h3>
                        <Activity className="text-amber-400 h-5 w-5" />
                    </div>
                    <p className="text-3xl font-bold text-white">
                        {profile?.spending_cap ? `$${profile.spending_cap}` : "None"}
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-4">Quick Actions</h3>
                    <div className="space-y-3">
                        <Link href="/dashboard/keys" className="flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 transition group">
                            <span className="flex items-center gap-3 text-sm font-medium"><Key size={16} className="text-indigo-400" /> Manage API Keys</span>
                            <span className="text-gray-400 text-xs group-hover:text-white transition">→</span>
                        </Link>
                        <Link href="/dashboard/billing" className="flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 transition group">
                            <span className="flex items-center gap-3 text-sm font-medium"><CreditCard size={16} className="text-emerald-400" /> Manage Subscription</span>
                            <span className="text-gray-400 text-xs group-hover:text-white transition">→</span>
                        </Link>
                        <Link href="/dashboard/team" className="flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 transition group">
                            <span className="flex items-center gap-3 text-sm font-medium"><Users size={16} className="text-purple-400" /> Team Management</span>
                            <span className="text-gray-400 text-xs group-hover:text-white transition">→</span>
                        </Link>
                        <Link href="/dashboard/usage" className="flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 transition group">
                            <span className="flex items-center gap-3 text-sm font-medium"><Activity size={16} className="text-amber-400" /> Usage History</span>
                            <span className="text-gray-400 text-xs group-hover:text-white transition">→</span>
                        </Link>
                    </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-4">Getting Started</h3>
                    <div className="space-y-4">
                        <div className="flex items-start gap-3">
                            <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">1</div>
                            <div>
                                <p className="text-sm font-medium">Add your API keys</p>
                                <p className="text-xs text-gray-400">Bring your own keys from OpenAI, Anthropic, Google, or others.</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">2</div>
                            <div>
                                <p className="text-sm font-medium">Install the terminal app</p>
                                <p className="text-xs text-gray-400">Run <code className="bg-gray-800 px-1.5 py-0.5 rounded text-indigo-300">pip install gptcgt</code> to get started.</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">3</div>
                            <div>
                                <p className="text-sm font-medium">Start coding</p>
                                <p className="text-xs text-gray-400">Open a project folder and launch gptcgt. The AI sees your code in context.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
