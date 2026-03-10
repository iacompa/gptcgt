"use client";

import Link from "next/link";
import {
    Activity,
    Bot,
    CreditCard,
    Github,
    Key,
    LogOut,
    MessageSquare,
    User,
    Users,
    Wallet,
} from "lucide-react";
import { usePathname } from "next/navigation";

export function DashboardNav({ session }: { session: any }) {
    const pathname = usePathname();

    const navigation = [
        { name: "Overview", href: "/dashboard", icon: Activity },
        { name: "Chat", href: "/dashboard/chat", icon: MessageSquare },
        { name: "Hub", href: "/dashboard/hub", icon: Github },
        { name: "API Keys", href: "/dashboard/keys", icon: Key },
        { name: "Billing", href: "/dashboard/billing", icon: CreditCard },
        { name: "Usage", href: "/dashboard/usage", icon: Activity },
        { name: "Team", href: "/dashboard/team", icon: Users },
        { name: "Account", href: "/dashboard/account", icon: User },
    ];

    const initials = (session?.user?.name || session?.user?.email || "U")
        .split(" ")
        .map((part: string) => part.charAt(0))
        .join("")
        .slice(0, 2)
        .toUpperCase();

    return (
        <div className="space-y-4">
            <div className="panel p-5">
                <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-sm font-semibold text-[var(--accent-strong)]">
                        {initials}
                    </div>
                    <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-950">
                            {session?.user?.name || "Developer"}
                        </p>
                        <p className="truncate text-sm text-[var(--text-muted)]">{session?.user?.email || ""}</p>
                    </div>
                </div>
                <div className="soft-divider my-5" />
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                    <div className="panel-muted p-4">
                        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
                            <Bot className="h-4 w-4 text-[var(--accent)]" />
                            Routing cockpit
                        </div>
                        <p className="mt-2 text-sm text-[var(--text-muted)]">
                            Chat, Hub, usage, and billing in one place.
                        </p>
                    </div>
                    <div className="panel-muted p-4">
                        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
                            <Wallet className="h-4 w-4 text-[var(--amber)]" />
                            Spend visible
                        </div>
                        <p className="mt-2 text-sm text-[var(--text-muted)]">
                            Wallet and cap signals stay close to the work.
                        </p>
                    </div>
                </div>
            </div>

            <div className="panel p-4">
                <p className="eyebrow px-2">Workspace</p>
                <nav className="mt-3 flex gap-2 overflow-x-auto pb-1 xl:flex-col">
                    {navigation.map((item) => {
                        const isOverview = item.href === "/dashboard";
                        const isActive = isOverview
                            ? pathname === item.href
                            : pathname === item.href || pathname.startsWith(`${item.href}/`);
                        return (
                            <Link
                                key={item.name}
                                href={item.href}
                                className={`flex min-w-fit items-center gap-3 rounded-2xl px-3 py-3 text-sm font-medium transition xl:min-w-0 ${
                                    isActive
                                        ? "bg-slate-950 text-white shadow-[0_12px_24px_rgba(15,23,42,0.16)]"
                                        : "text-[var(--text-muted)] hover:bg-white/70 hover:text-slate-950"
                                }`}
                            >
                                <item.icon className={`h-4 w-4 ${isActive ? "text-amber-300" : ""}`} />
                                {item.name}
                            </Link>
                        );
                    })}
                </nav>
                <div className="soft-divider my-4" />
                <button
                    onClick={async () => {
                        await fetch("/api/auth/signout", { method: "POST" });
                        window.location.href = "/";
                    }}
                    className="btn-ghost w-full justify-start text-red-700 hover:bg-red-50"
                >
                    <LogOut className="h-4 w-4" /> Sign out
                </button>
            </div>
        </div>
    );
}
