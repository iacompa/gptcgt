"use client";

import { useCallback, useEffect, useState } from "react";
import { UserPlus, Mail, Shield, CheckCircle2, Trash2, Clock, Users, AlertTriangle } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface TeamMember {
    id: string;
    email: string;
    role: string;
    status: string;
    joined: string;
}

interface PendingInvite {
    id: string;
    email: string;
    role: string;
    created_at: string;
}

export default function TeamPage() {
    const [profile, setProfile] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("member");
    const [inviting, setInviting] = useState(false);
    const [inviteError, setInviteError] = useState("");
    const [inviteSuccess, setInviteSuccess] = useState("");
    const [pendingInvites, setPendingInvites] = useState<PendingInvite[]>([]);
    const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);

    const members = profile ? [
        { id: "self", email: profile.email, role: profile.team_role || "Owner", status: "Active", joined: "—" },
        ...teamMembers,
    ] : [];

    const loadTeamData = useCallback(async () => {
        try {
            const [rawMembersRes, invitesRes] = await Promise.all([
                apiClient.GET("/team/"),
                apiClient.GET("/team/invites/pending"),
            ]);
            const rawMembers = (rawMembersRes.data as any[]) || [];
            const invites = (invitesRes.data as any[]) || [];
            const mapped = (rawMembers || []).map((m: any) => ({
                ...m,
                status: "Active",
            }));
            setTeamMembers(mapped);
            setPendingInvites(invites || []);
        } catch (e) {
            console.error(e);
        }
    }, []);

    const loadProfile = useCallback(async () => {
        try {
            const { data, error } = await apiClient.GET("/user/me");
            if (error) throw error;
            const profileData = data as any;
            setProfile(profileData);

            if (profileData.plan === "team" || profileData.plan === "enterprise") {
                await loadTeamData();
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [loadTeamData]);

    useEffect(() => {
        loadProfile();
    }, [loadProfile]);

    const handleInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inviteEmail.trim() || inviting) return;

        setInviting(true);
        setInviteError("");
        setInviteSuccess("");

        try {
            const { error } = await apiClient.POST("/team/invites/invite", {
                body: { email: inviteEmail, role: inviteRole } as any
            });
            if (error) throw error;
            setInviteSuccess(`Invite sent to ${inviteEmail}`);
            setInviteEmail("");
            await loadTeamData();
            setTimeout(() => setInviteSuccess(""), 5000);
        } catch (err: any) {
            setInviteError(err.message || "Failed to send invite");
        } finally {
            setInviting(false);
        }
    };

    const handleRemoveMember = async (userId: string) => {
        if (!confirm("Remove this member from the team?")) return;
        try {
            const { error } = await apiClient.DELETE("/team/invites/member", {
                body: { target_user_id: userId } as any
            });
            if (error) throw error;
            await loadTeamData();
        } catch (err: any) {
            alert(err.message || "Failed to remove member");
        }
    };

    const isTeamPlan = profile?.plan === "team" || profile?.plan === "enterprise";
    const isOwnerOrAdmin = profile?.team_role === "owner" || profile?.team_role === "admin";

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full" />
            </div>
        );
    }

    return (
        <div className="max-w-5xl">
            <div className="flex justify-between items-end mb-6">
                <div>
                    <h1 className="text-2xl font-bold">Team Members</h1>
                    <p className="text-gray-400 mt-1">Manage organization access and unified billing.</p>
                </div>
                {isTeamPlan && (
                    <span className="text-xs text-gray-500 flex items-center gap-1.5">
                        <Users className="w-3.5 h-3.5" />
                        {members.length} {members.length === 1 ? "member" : "members"}
                    </span>
                )}
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
                    <a href="/pricing" className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-lg font-bold shadow-lg shadow-indigo-500/20 transition-colors">
                        View Plans & Pricing
                    </a>
                </div>
            )}

            {/* Invite Form — functional for team plans */}
            {isTeamPlan && isOwnerOrAdmin && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
                    <div className="flex justify-between items-center mb-1">
                        <h3 className="font-bold">Invite Member</h3>
                    </div>
                    <p className="text-sm text-gray-400 mb-4">Send an email invitation to join your organization workspace.</p>

                    <form onSubmit={handleInvite} className="flex gap-3">
                        <div className="relative flex-1">
                            <Mail className="absolute left-3 top-2.5 h-5 w-5 text-gray-500" />
                            <input
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="colleague@domain.com"
                                required
                                className="w-full bg-gray-950 border border-gray-700 rounded-md pl-10 pr-4 py-2 text-white focus:outline-none focus:border-indigo-500 transition-colors"
                            />
                        </div>
                        <select
                            value={inviteRole}
                            onChange={(e) => setInviteRole(e.target.value)}
                            className="bg-gray-950 border border-gray-700 rounded-md px-4 py-2 text-white focus:outline-none focus:border-indigo-500 w-32"
                        >
                            <option value="member">Member</option>
                            <option value="admin">Admin</option>
                        </select>
                        <button
                            type="submit"
                            disabled={inviting || !inviteEmail.trim()}
                            className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-md font-medium flex items-center gap-2 transition-colors"
                        >
                            <UserPlus size={18} />
                            {inviting ? "Sending..." : "Send Invite"}
                        </button>
                    </form>

                    {inviteError && (
                        <div className="mt-3 text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-md p-2 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {inviteError}
                        </div>
                    )}
                    {inviteSuccess && (
                        <div className="mt-3 text-sm text-emerald-400 bg-emerald-950/30 border border-emerald-900/50 rounded-md p-2 flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> {inviteSuccess}
                        </div>
                    )}
                </div>
            )}

            {/* Pending Invites */}
            {isTeamPlan && pendingInvites.length > 0 && (
                <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 mb-6">
                    <h3 className="text-sm font-bold text-gray-400 mb-3 flex items-center gap-2">
                        <Clock className="w-4 h-4" /> Pending Invitations
                    </h3>
                    <div className="space-y-2">
                        {pendingInvites.map((invite) => (
                            <div key={invite.id} className="flex items-center justify-between bg-gray-900 rounded-lg px-4 py-2.5">
                                <div>
                                    <span className="text-sm font-medium">{invite.email}</span>
                                    <span className="ml-3 text-xs bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded">
                                        {invite.role}
                                    </span>
                                </div>
                                <span className="text-xs text-gray-500">
                                    Sent {new Date(invite.created_at).toLocaleDateString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Members Table */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-gray-800 text-gray-400">
                        <tr>
                            <th className="px-6 py-3 font-medium">USER</th>
                            <th className="px-6 py-3 font-medium">ROLE</th>
                            <th className="px-6 py-3 font-medium">STATUS</th>
                            <th className="px-6 py-3 font-medium text-right">ACTIONS</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {members.map((member) => (
                            <tr key={member.id} className="hover:bg-gray-800/50">
                                <td className="px-6 py-4 font-medium">{member.email}</td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 rounded text-xs font-semibold ${member.role === "owner" || member.role === "Owner"
                                        ? "bg-amber-500/10 text-amber-400"
                                        : member.role === "admin"
                                            ? "bg-indigo-500/10 text-indigo-400"
                                            : "bg-gray-700/50 text-gray-400"
                                        }`}>
                                        {member.role}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <span className="flex items-center gap-1 text-emerald-400">
                                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                        {member.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-right">
                                    {isOwnerOrAdmin && member.id !== "self" && member.role !== "owner" && member.role !== "Owner" && (
                                        <button
                                            onClick={() => handleRemoveMember(member.id)}
                                            className="text-gray-500 hover:text-red-400 transition-colors p-1"
                                            title="Remove member"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
