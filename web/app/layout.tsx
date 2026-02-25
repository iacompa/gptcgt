import "./globals.css";
import React from "react";
import Link from "next/link";
import { Footer } from "@/components/footer";

export const metadata = {
    title: "GPTCGT - Agentic Capabilities at Scale",
    description: "Manage your AI pipeline, API keys, and spending limits.",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark">
            <body className="font-sans bg-gray-950 text-gray-100 antialiased h-screen flex flex-col">
                <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-md sticky top-0 z-50">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                        <div className="flex items-center justify-between h-16">
                            <div className="flex items-center gap-4">
                                <Link href="/" className="font-bold text-xl tracking-tight text-white flex items-center gap-2">
                                    <div className="w-8 h-8 rounded bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold">
                                        G
                                    </div>
                                    GPTCGT
                                </Link>
                                <nav className="hidden md:ml-6 md:flex md:space-x-4">
                                    <Link href="/pricing" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Pricing</Link>
                                    <Link href="/docs" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Docs</Link>
                                    <Link href="/dashboard" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Dashboard</Link>
                                </nav>
                            </div>
                            <div>
                                <Link href="/auth" className="bg-white text-black px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-200 transition-colors">
                                    Sign In
                                </Link>
                            </div>
                        </div>
                    </div>
                </header>

                <main className="flex-1 overflow-auto relative">
                    {children}
                </main>
                <Footer />
            </body>
        </html>
    );
}
