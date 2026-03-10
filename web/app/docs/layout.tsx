import Link from 'next/link';
import {
    Book, Cpu, Keyboard, Key, Sliders, DollarSign,
    Database, HelpCircle, Bot, Shield, Trophy, Layers,
} from 'lucide-react';

const DOCS_NAV = [
    { name: 'Overview', href: '/docs', icon: Book },
    { name: 'Getting Started', href: '/docs/getting-started', icon: Layers },
    { name: 'Operation Modes', href: '/docs/modes', icon: Cpu },
    { name: 'Autonomous Mode', href: '/docs/autonomous', icon: Bot },
    { name: 'Commands & Shortcuts', href: '/docs/commands', icon: Keyboard },
    { name: 'API Keys & Auth', href: '/docs/keys', icon: Key },
    { name: 'Configuration', href: '/docs/config', icon: Sliders },
    { name: 'Costs & Billing', href: '/docs/costs', icon: DollarSign },
    { name: 'ELO Arena', href: '/docs/elo-arena', icon: Trophy },
    { name: 'Security & Safety', href: '/docs/security', icon: Shield },
    { name: 'Custom Models', href: '/docs/custom-models', icon: Database },
    { name: 'FAQ', href: '/docs/faq', icon: HelpCircle },
];

export default function DocsLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="page-shell">
            <div className="grid min-h-[calc(100vh-10rem)] gap-6 lg:grid-cols-[280px_1fr]">
            {/* Sidebar nav */}
                <nav className="panel hidden h-fit p-4 lg:sticky lg:top-24 lg:block">
                    <p className="eyebrow px-3">Documentation</p>
                    <div className="mt-3 space-y-1">
                    {DOCS_NAV.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                                className="flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-[var(--text-muted)] transition hover:bg-white/70 hover:text-slate-950"
                        >
                            <item.icon className="w-4 h-4 flex-shrink-0" />
                            {item.name}
                        </Link>
                    ))}
                    </div>
                </nav>

            {/* Main content */}
                <main className="panel-dark overflow-auto p-6 sm:p-8">
                    <div className="prose prose-invert max-w-3xl prose-headings:tracking-[-0.03em] prose-headings:text-white prose-p:text-slate-300 prose-a:text-emerald-300 prose-a:no-underline hover:prose-a:text-emerald-200 prose-code:text-emerald-200 prose-code:before:hidden prose-code:after:hidden prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-lg prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/10 prose-strong:text-white prose-li:text-slate-300">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
