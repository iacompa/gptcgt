"use client";

import Link from "next/link";
import { Activity, Key, CreditCard, Users, User, LogOut, MessageSquare, Github } from "lucide-react";
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

    return (
        <div className="w-64 border-r border-gray-800 bg-gray-900/30 flex flex-col h-full">
            <div className="p-6">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">
                        {session?.user?.name?.charAt(0) || "U"}
                    </div>
                    <div className="overflow-hidden">
                        <p className="text-sm font-medium text-white truncate">{session?.user?.name || "Developer"}</p>
                        <p className="text-xs text-gray-500 truncate">{session?.user?.email || ""}</p>
                    </div>
                </div>
            </div>

            <nav className="flex-1 px-4 space-y-1">
                {navigation.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md ${isActive
                                ? "bg-gray-800 text-white"
                                : "text-gray-300 hover:bg-gray-800 hover:text-white"
                                }`}
                        >
                            <item.icon className="text-gray-400 group-hover:text-gray-300 mr-3 flex-shrink-0 h-5 w-5" />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            <div className="p-4 border-t border-gray-800">
                <button
                    onClick={async () => {
                        await fetch("/api/auth/signout", { method: "POST" });
                        window.location.href = "/";
                    }}
                    className="text-gray-400 hover:text-red-400 flex items-center gap-2 text-sm px-2 transition-colors w-full"
                >
                    <LogOut className="h-4 w-4" /> Sign Out
                </button>
            </div>
        </div>
    );
}
