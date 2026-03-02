import { LifeBuoy, Mail, TerminalSquare, FileSearch, ShieldAlert } from 'lucide-react';
import Link from 'next/link';

export default function SupportPage() {
    return (
        <div className="relative isolate px-6 py-24 sm:py-32 lg:px-8 max-w-7xl mx-auto">
            <div className="mx-auto max-w-3xl text-center">
                <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">Support Hub</h1>
                <p className="mt-6 text-lg leading-8 text-gray-400">
                    We're here to help you debug the terminal, manage your account, and maximize your Multi-Model workflow.
                </p>
            </div>

            <div className="mx-auto mt-16 max-w-4xl grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-2">

                {/* Documentation Block */}
                <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 flex flex-col gap-4">
                    <div className="h-12 w-12 rounded-lg bg-indigo-500/10 flex items-center justify-center">
                        <TerminalSquare className="h-6 w-6 text-indigo-400" />
                    </div>
                    <h3 className="text-xl font-bold text-white">CLI Documentation</h3>
                    <p className="text-gray-400">
                        Check our comprehensive guides on configuring local models, managing BYOK credentials, and understanding the ELO routing system.
                    </p>
                    <Link href="/docs" className="mt-auto text-indigo-400 font-semibold hover:text-indigo-300">
                        Read the Docs &rarr;
                    </Link>
                </div>

                {/* Direct Email Block */}
                <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 flex flex-col gap-4">
                    <div className="h-12 w-12 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                        <Mail className="h-6 w-6 text-emerald-400" />
                    </div>
                    <h3 className="text-xl font-bold text-white">Contact Us Directly</h3>
                    <p className="text-gray-400">
                        Have an account issue, billing question, or encountered a terminal crash? Email our engineering team directly.
                    </p>
                    <a href="mailto:support@gptcgt.ai" className="mt-auto text-emerald-400 font-semibold hover:text-emerald-300">
                        support@gptcgt.ai &rarr;
                    </a>
                </div>

                {/* Security Block */}
                <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 flex flex-col gap-4">
                    <div className="h-12 w-12 rounded-lg bg-orange-500/10 flex items-center justify-center">
                        <ShieldAlert className="h-6 w-6 text-orange-400" />
                    </div>
                    <h3 className="text-xl font-bold text-white">Responsible Disclosure</h3>
                    <p className="text-gray-400">
                        Found a vulnerability in our proxy routing or CLI environment access? Please report it confidentially.
                    </p>
                    <Link href="/privacy" className="mt-auto text-orange-400 font-semibold hover:text-orange-300">
                        View Privacy Policy &rarr;
                    </Link>
                </div>

                {/* Billing FAQ Block */}
                <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 flex flex-col gap-4">
                    <div className="h-12 w-12 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <FileSearch className="h-6 w-6 text-blue-400" />
                    </div>
                    <h3 className="text-xl font-bold text-white">Credit & Billing FAQ</h3>
                    <p className="text-gray-400">
                        Understand how the Pro Tier token conversion works across different model providers.
                    </p>
                    <Link href="/pricing" className="mt-auto text-blue-400 font-semibold hover:text-blue-300">
                        View Pricing Plans &rarr;
                    </Link>
                </div>
            </div>

            <div className="mt-20 text-center">
                <p className="text-gray-500 text-sm">
                    Response times: Pro Tier customers typically receive responses within 24 hours on business days.<br />
                    BYOK (Free Tier) support is handled on a best-effort basis.
                </p>
            </div>
        </div>
    );
}
