"use client";

import { useState, useEffect } from "react";
import { UserPlus, Mail, Shield, CheckCircle2 } from "lucide-react";
import { fetchAPI } from "@/lib/api";

export default function TeamPage() {
    const [profile, setProfile] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    const members = profile ? [
        { id: "1", email: profile.email, role: "Owner", status: "Active", joined: "Today" }
    ] : [];

    useEffect(() => {
        loadProfile();
    }, []);

    const loadProfile = async () => {
        try {
            const data = await fetchAPI("/user/me");
            setProfile(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const isTeamPlan = profile?.plan === "team" || profile?.plan === "enterprise";

    if (loading) return <div>Loading...</div>;

    return (
        <div className="max-w-5xl">
            <div className="flex justify-between items-end mb-6">
                <div>
                    <h1 className="text-2xl font-bold">Team Members</h1>
                    <p className="text-gray-400 mt-1">Manage organization access and unified billing.</p>
                </div>
            </div>

            {!isTeamPlan && (
                <div className="bg-gradient-to-r from-indigo-900/40 to-purple-900/40 border border-indigo-500/30 rounded-xl p-8 mb-8 flex flex-col items-center justify-center text-center">
                    <Shield className="w-12 h-12 text-indigo-400 mb-4" />
                    <h2 className="text-xl font-bold mb-2">Upgrade to Team</h2>
                    <p className="text-gray-300 max-w-lg mb-6">
                        Unlock organization keys, unified billing, and collaborative orchestrations by upgrading your plan.
                    </p>
                    <ul className="text-sm text-gray-400 space-y-2 mb-8 text-left">
                        <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Add up to 10 members</li>
                        <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Shared proxy cap management</li>
                        <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Single invoice for all developers</li>
                    </ul>
                    <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-lg font-bold shadow-lg shadow-indigo-500/20">
                        View Plans & Pricing
                    </button>
                </div>
            )}

            {isTeamPlan && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8 flex gap-4">
                    <div className="flex-1">
                        <div className="flex justify-between items-center mb-1">
                            <h3 className="font-bold">Invite Member</h3>
                            <span className="bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider">Coming Soon</span>
                        </div>
                        <p className="text-sm text-gray-400 mb-4">Send an email invitation to join your organization workspace.</p>
                        <div className="flex gap-3 relative overflow-hidden">
                            <div className="absolute inset-0 bg-gray-900/50 backdrop-blur-[1px] z-10 hidden"></div>
                            <div className="relative flex-1 opacity-50">
                                <Mail className="absolute left-3 top-2.5 h-5 w-5 text-gray-500" />
                                <input
                                    type="email"
                                    placeholder="colleague@domain.com"
                                    className="w-full bg-gray-950 border border-gray-700 rounded-md pl-10 pr-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                                    disabled
                                />
                            </div>
                            <select disabled className="opacity-50 bg-gray-950 border border-gray-700 rounded-md px-4 py-2 text-white focus:outline-none focus:border-indigo-500 w-32">
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                            </select>
                            <button disabled className="opacity-50 cursor-not-allowed bg-indigo-600/50 hover:bg-indigo-600/50 text-white px-4 py-2 rounded-md font-medium flex items-center gap-2">
                                <UserPlus size={18} /> Send Invite
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden relative">
                {isTeamPlan && (
                    <div className="absolute top-3 right-6 bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider hidden">Coming Soon</div>
                )}
                <table className="w-full text-left text-sm">
                    <thead className="bg-gray-800 text-gray-400">
                        <tr>
                            <th className="px-6 py-3 font-medium">USER</th>
                            <th className="px-6 py-3 font-medium">ROLE</th>
                            <th className="px-6 py-3 font-medium">STATUS</th>
                            <th className="px-6 py-3 font-medium text-right">JOINED</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {members.map((member) => (
                            <tr key={member.id} className="hover:bg-gray-800/50">
                                <td className="px-6 py-4 font-medium">{member.email}</td>
                                <td className="px-6 py-4">
                                    <span className="bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded text-xs font-semibold">
                                        {member.role}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <span className="flex items-center gap-1 text-emerald-400">
                                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                        {member.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-right text-gray-400">{member.joined}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
