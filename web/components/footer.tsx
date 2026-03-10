import Link from "next/link";

export function Footer() {
    const currentYear = new Date().getFullYear();
    return (
        <footer className="border-t border-[color:var(--border)] py-12">
            <div className="page-shell">
                <div className="panel flex flex-col gap-6 px-6 py-8 lg:flex-row lg:items-end lg:justify-between lg:px-8">
                    <div>
                        <p className="eyebrow">gptcgt</p>
                        <p className="mt-3 max-w-xl text-lg font-medium tracking-[-0.03em] text-slate-950">
                            A calmer control surface for multi-model coding, proof-backed automation, and transparent cost decisions.
                        </p>
                        <p className="mt-3 copy-sm">© {currentYear} IA Compa LLC. All rights reserved.</p>
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm text-[var(--text-muted)]">
                        <Link href="/terms" className="btn-ghost">
                            Terms
                        </Link>
                        <Link href="/privacy" className="btn-ghost">
                            Privacy
                        </Link>
                        <Link href="/acceptable-use" className="btn-ghost">
                            Use policy
                        </Link>
                        <Link href="/support" className="btn-ghost">
                            Support
                        </Link>
                    </div>
                </div>
            </div>
        </footer>
    );
}
