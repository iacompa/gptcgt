import "./globals.css";
import React from "react";
import Link from "next/link";
import Image from "next/image";
import { Footer } from "@/components/footer";

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
        <html lang="en" className="dark">
            <body className="font-sans bg-gray-950 text-gray-100 antialiased">
                <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-md">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                        <div className="flex items-center justify-between h-16">
                            <div className="flex items-center gap-4">
                                <Link href="/" className="font-bold text-xl tracking-tight text-white flex items-center gap-2">
                                    <Image src="/logo.svg" alt="gptcgt logo" width={32} height={32} className="rounded-md" />
                                    <span className="flex">
                                        <span className="text-emerald-400">gpt</span>
                                        <span className="text-orange-400">c</span>
                                        <span className="text-blue-400">g</span>
                                        <span className="text-purple-400">t</span>
                                    </span>
                                </Link>
                                <nav className="hidden md:ml-6 md:flex md:space-x-4">
                                    <Link href="/pricing" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Pricing</Link>
                                    <Link href="/docs" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Docs</Link>
                                    {isAuthenticated && (
                                        <Link href="/dashboard" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Dashboard</Link>
                                    )}
                                </nav>
                            </div>
                            <div className="flex items-center gap-4">
                                {isAuthenticated ? (
                                    <>
                                        <Link href="/dashboard" className="text-sm font-medium hover:text-gray-300 transition-colors">
                                            Dashboard
                                        </Link>
                                        <Link href="/api/auth/signout" className="bg-gray-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                                            Sign Out
                                        </Link>
                                    </>
                                ) : (
                                    <Link href="/auth" className="bg-white text-black px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-200 transition-colors">
                                        Sign In
                                    </Link>
                                )}
                            </div>
                        </div>
                    </div>
                </header>

                <main className="flex-1 relative">
                    {children}
                </main>
                <Footer />
            </body>
        </html>
    );
}
