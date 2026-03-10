"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock, Mail, Shield, Trash2, UserPlus, Users } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { useToast } from "@/components/toaster";

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
    const [pendingInvites, setPendingInvites] = useState<PendingInvite[]>([]);
    const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
    const [memberToRemove, setMemberToRemove] = useState<TeamMember | null>(null);
    const [isRemoving, setIsRemoving] = useState(false);
    const { pushToast } = useToast();

    const members = profile
        ? teamMembers.some((member) => member.email === profile.email)
            ? teamMembers
            : [
                  {
                      id: "self",
                      email: profile.email,
                      role: profile.team_role || "Owner",
                      status: "Active",
                      joined: "—",
                  },
                  ...teamMembers,
              ]
        : [];

    const loadTeamData = useCallback(async () => {
        try {
            const [rawMembersRes, invitesRes] = await Promise.all([
                apiClient.GET("/team/"),
                apiClient.GET("/team/invites/pending"),
            ]);
            const rawMembers = (rawMembersRes.data as any[]) || [];
            const invites = (invitesRes.data as any[]) || [];
            setTeamMembers(
                rawMembers.map((member: any) => ({
                    ...member,
                    status: "Active",
                }))
            );
            setPendingInvites(invites || []);
        } catch (error) {
            console.error(error);
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
        } catch (error: any) {
            console.error(error);
            pushToast({
                tone: "error",
                title: "Could not load team profile",
                description: error.message,
            });
        } finally {
            setLoading(false);
        }
    }, [loadTeamData, pushToast]);

    useEffect(() => {
        void loadProfile();
    }, [loadProfile]);

    const handleInvite = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!inviteEmail.trim() || inviting) return;
        setInviting(true);

        try {
            const { error } = await apiClient.POST("/team/invites/invite", {
                body: { email: inviteEmail, role: inviteRole } as any,
            });
            if (error) throw error;
            pushToast({
                tone: "success",
                title: "Invite sent",
                description: `Invitation sent to ${inviteEmail}.`,
            });
            setInviteEmail("");
            await loadTeamData();
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "Failed to send invite",
                description: error.message || "Please verify the email address and permissions.",
            });
        } finally {
            setInviting(false);
        }
    };

    const removeMember = async () => {
        if (!memberToRemove) return;
        setIsRemoving(true);
        try {
            const { error } = await apiClient.DELETE("/team/invites/member", {
                body: { target_user_id: memberToRemove.id } as any,
            });
            if (error) throw error;
            pushToast({
                tone: "success",
                title: "Member removed",
                description: `${memberToRemove.email} was removed from the team workspace.`,
            });
            setMemberToRemove(null);
            await loadTeamData();
        } catch (error: any) {
            pushToast({
                tone: "error",
                title: "Failed to remove member",
                description: error.message,
            });
        } finally {
            setIsRemoving(false);
        }
    };

    const isTeamPlan = profile?.plan === "team" || profile?.plan === "enterprise";
    const isOwnerOrAdmin = profile?.team_role === "owner" || profile?.team_role === "admin";

    if (loading) {
        return <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">Loading team workspace...</div>;
    }

    return (
        <div className="page-stack">
            <section className="hero-panel p-6 sm:p-8">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="eyebrow">Team</p>
                        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">
                            Manage shared access without losing sight of billing or role ownership.
                        </h1>
                        <p className="mt-3 max-w-3xl copy-lg">
                            Team membership, invites, and shared wallet behavior belong in the same operational surface.
                        </p>
                    </div>
                    {isTeamPlan && (
                        <div className="badge badge-accent">
                            <Users className="h-3.5 w-3.5" /> {members.length} members
                        </div>
                    )}
                </div>
            </section>

            {!isTeamPlan && (
                <section className="panel p-6 sm:p-8">
                    <div className="flex flex-col items-start gap-4 sm:flex-row">
                        <div className="rounded-2xl bg-[var(--accent-soft)] p-3 text-[var(--accent-strong)]">
                            <Shield className="h-6 w-6" />
                        </div>
                        <div>
                            <h2 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">Upgrade to a team workspace</h2>
                            <p className="mt-3 max-w-2xl text-sm text-[var(--text-muted)]">
                                Shared keys, unified billing, and collaborative orchestrations only make sense when the team surface is built around them.
                            </p>
                            <div className="mt-5 flex flex-wrap gap-3">
                                <span className="badge badge-accent">Shared wallet</span>
                                <span className="badge badge-accent">Member roles</span>
                                <span className="badge badge-accent">Unified billing</span>
                            </div>
                            <a href="/pricing" className="btn-primary mt-6 inline-flex">
                                View plans
                            </a>
                        </div>
                    </div>
                </section>
            )}

            {isTeamPlan && isOwnerOrAdmin && (
                <section className="panel p-6">
                    <div className="flex items-center gap-2">
                        <UserPlus className="h-5 w-5 text-[var(--accent)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Invite a teammate</h2>
                    </div>
                    <p className="mt-3 text-sm text-[var(--text-muted)]">
                        Invite an engineer into the shared workspace and give them the right level of access from the start.
                    </p>
                    <form onSubmit={handleInvite} className="mt-5 grid gap-4 lg:grid-cols-[1fr_160px_auto]">
                        <div className="relative">
                            <Mail className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-[var(--text-soft)]" />
                            <input
                                type="email"
                                value={inviteEmail}
                                onChange={(event) => setInviteEmail(event.target.value)}
                                placeholder="colleague@domain.com"
                                required
                                className="field pl-11"
                            />
                        </div>
                        <select
                            value={inviteRole}
                            onChange={(event) => setInviteRole(event.target.value)}
                            className="select-field"
                        >
                            <option value="member">Member</option>
                            <option value="admin">Admin</option>
                        </select>
                        <button type="submit" disabled={inviting || !inviteEmail.trim()} className="btn-primary">
                            {inviting ? "Sending..." : "Send invite"}
                        </button>
                    </form>
                </section>
            )}

            {isTeamPlan && pendingInvites.length > 0 && (
                <section className="panel p-6">
                    <div className="flex items-center gap-2">
                        <Clock className="h-5 w-5 text-[var(--amber)]" />
                        <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Pending invitations</h2>
                    </div>
                    <div className="mt-5 space-y-3">
                        {pendingInvites.map((invite) => (
                            <div key={invite.id} className="panel-muted flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                    <p className="text-sm font-semibold text-slate-950">{invite.email}</p>
                                    <p className="mt-1 text-sm text-[var(--text-muted)]">Role: {invite.role}</p>
                                </div>
                                <span className="text-sm text-[var(--text-soft)]">
                                    Sent {new Date(invite.created_at).toLocaleDateString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {isTeamPlan && (
                <section className="table-shell">
                    <table>
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th className="text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {members.map((member) => (
                                <tr key={member.id}>
                                    <td className="font-medium text-slate-900">{member.email}</td>
                                    <td>
                                        <span
                                            className={`badge ${
                                                member.role === "owner" || member.role === "Owner"
                                                    ? "badge-amber"
                                                    : member.role === "admin"
                                                      ? "badge-accent"
                                                      : "bg-slate-900/5 text-slate-700"
                                            }`}
                                        >
                                            {member.role}
                                        </span>
                                    </td>
                                    <td>
                                        <span className="inline-flex items-center gap-2 text-sm text-[var(--accent-strong)]">
                                            <CheckCircle2 className="h-4 w-4" /> {member.status}
                                        </span>
                                    </td>
                                    <td className="text-right">
                                        {isOwnerOrAdmin &&
                                            member.id !== "self" &&
                                            member.role !== "owner" &&
                                            member.role !== "Owner" && (
                                                <button
                                                    type="button"
                                                    onClick={() => setMemberToRemove(member)}
                                                    className="btn-ghost ml-auto text-red-700 hover:bg-red-50"
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                    Remove
                                                </button>
                                            )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>
            )}

            <ConfirmDialog
                open={!!memberToRemove}
                title="Remove teammate?"
                description={
                    memberToRemove
                        ? `This removes ${memberToRemove.email} from the shared workspace and revokes their team access.`
                        : ""
                }
                confirmLabel="Remove member"
                busy={isRemoving}
                onCancel={() => setMemberToRemove(null)}
                onConfirm={removeMember}
            />
        </div>
    );
}
