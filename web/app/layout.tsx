import "./globals.css";
import React from "react";
import Link from "next/link";
import Image from "next/image";
import { Footer } from "@/components/footer";
import { AppProviders } from "@/components/app-providers";

import { getSession } from "@/lib/auth";

export const metadata = {
    title: "gptcgt - Multi-Model AI Coding Terminal",
    description: "Run multiple AIs on your code. Pick the best solution with proof. Terminal-native, provider-agnostic, with transparent cost tracking.",
    icons: {
        icon: "/favicon.svg",
    },
};

export default async function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const session = await getSession();
    const isAuthenticated = !!session?.user;

    return (
        <html lang="en">
            <body className="antialiased">
                <div className="grain" />
                <AppProviders>
                    <div className="relative flex min-h-screen flex-col">
                        <header className="sticky top-0 z-40 border-b border-[color:var(--border)] bg-[rgba(255,250,242,0.82)] backdrop-blur-xl">
                            <div className="page-shell py-4">
                                <div className="flex flex-wrap items-center justify-between gap-4">
                                    <div className="flex items-center gap-3">
                                        <Link
                                            href="/"
                                            className="flex items-center gap-3 rounded-full border border-[color:var(--border)] bg-white/75 px-3 py-2 shadow-sm transition hover:bg-white"
                                        >
                                            <Image
                                                src="/gcgt-icon-2a.png"
                                                alt=""
                                                width={34}
                                                height={34}
                                                className="rounded-xl shadow-sm"
                                                priority
                                            />
                                            <div>
                                                <p className="text-sm font-semibold tracking-[-0.02em] text-slate-950">gptcgt</p>
                                                <p className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--text-soft)]">
                                                    routing terminal
                                                </p>
                                            </div>
                                        </Link>
                                        <div className="hidden lg:block">
                                            <p className="copy-sm max-w-sm">
                                                Compare models, control spend, and ship repo-aware runs with proof attached.
                                            </p>
                                        </div>
                                    </div>

                                    <nav className="order-3 flex w-full items-center gap-2 overflow-x-auto sm:order-2 sm:w-auto">
                                        <Link href="/pricing" className="btn-ghost whitespace-nowrap">
                                            Pricing
                                        </Link>
                                        <Link href="/docs" className="btn-ghost whitespace-nowrap">
                                            Docs
                                        </Link>
                                        <Link href="/support" className="btn-ghost whitespace-nowrap">
                                            Support
                                        </Link>
                                        {isAuthenticated && (
                                            <Link href="/dashboard" className="btn-ghost whitespace-nowrap">
                                                Dashboard
                                            </Link>
                                        )}
                                    </nav>

                                    <div className="flex items-center gap-3">
                                        {isAuthenticated ? (
                                            <>
                                                <div className="hidden rounded-full bg-white/70 px-4 py-2 text-sm text-[var(--text-muted)] md:block">
                                                    Signed in as{" "}
                                                    <span className="font-medium text-slate-900">{session?.user?.email}</span>
                                                </div>
                                                <form action="/api/auth/signout" method="POST">
                                                    <button type="submit" className="btn-secondary">
                                                        Sign out
                                                    </button>
                                                </form>
                                            </>
                                        ) : (
                                            <Link href="/auth" className="btn-primary">
                                                Sign in
                                            </Link>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </header>

                        <main className="relative flex-1 py-8 sm:py-10">{children}</main>
                        <Footer />
                    </div>
                </AppProviders>
            </body>
        </html>
    );
}
