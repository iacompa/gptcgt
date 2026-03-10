import { LifeBuoy, Mail, TerminalSquare, FileSearch, ShieldAlert } from 'lucide-react';
import Link from 'next/link';

export default function SupportPage() {
    return (
        <div className="page-shell page-stack">
            <div className="hero-panel px-6 py-10 text-center sm:px-10">
                <p className="eyebrow">Support</p>
                <h1 className="mt-3 text-4xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-5xl">
                    Get help without hunting through disconnected pages.
                </h1>
                <p className="mx-auto mt-4 max-w-3xl copy-lg">
                    Documentation, billing questions, direct contact, and disclosure paths should be one clear surface.
                </p>
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">

                {/* Documentation Block */}
                <div className="panel flex flex-col gap-4 p-8">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent-soft)]">
                        <TerminalSquare className="h-6 w-6 text-[var(--accent)]" />
                    </div>
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">CLI documentation</h3>
                    <p className="text-[var(--text-muted)]">
                        Check our comprehensive guides on configuring local models, managing BYOK credentials, and understanding the ELO routing system.
                    </p>
                    <Link href="/docs" className="mt-auto font-semibold text-[var(--accent)] hover:text-[var(--accent-strong)]">
                        Read the Docs &rarr;
                    </Link>
                </div>

                {/* Direct Email Block */}
                <div className="panel flex flex-col gap-4 p-8">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent-soft)]">
                        <Mail className="h-6 w-6 text-[var(--accent)]" />
                    </div>
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Contact us directly</h3>
                    <p className="text-[var(--text-muted)]">
                        Have an account issue, billing question, or encountered a terminal crash? Email our engineering team directly.
                    </p>
                    <a href="mailto:support@gptcgt.ai" className="mt-auto font-semibold text-[var(--accent)] hover:text-[var(--accent-strong)]">
                        support@gptcgt.ai &rarr;
                    </a>
                </div>

                {/* Security Block */}
                <div className="panel flex flex-col gap-4 p-8">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--amber-soft)]">
                        <ShieldAlert className="h-6 w-6 text-[var(--amber)]" />
                    </div>
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Responsible disclosure</h3>
                    <p className="text-[var(--text-muted)]">
                        Found a vulnerability in our proxy routing or CLI environment access? Please report it confidentially.
                    </p>
                    <Link href="/privacy" className="mt-auto font-semibold text-[var(--amber)] hover:text-orange-700">
                        View Privacy Policy &rarr;
                    </Link>
                </div>

                {/* Billing FAQ Block */}
                <div className="panel flex flex-col gap-4 p-8">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900/5">
                        <FileSearch className="h-6 w-6 text-slate-900" />
                    </div>
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Credit & billing FAQ</h3>
                    <p className="text-[var(--text-muted)]">
                        Understand how the Pro Tier token conversion works across different model providers.
                    </p>
                    <Link href="/pricing" className="mt-auto font-semibold text-slate-900 hover:text-[var(--accent)]">
                        View Pricing Plans &rarr;
                    </Link>
                </div>
            </div>

            <div className="panel p-6 text-center">
                <p className="text-sm text-[var(--text-muted)]">
                    Response times: Pro Tier customers typically receive responses within 24 hours on business days.<br />
                    BYOK (Free Tier) support is handled on a best-effort basis.
                </p>
            </div>
        </div>
    );
}
