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
        <div className="flex min-h-[calc(100vh-4rem)] bg-gray-950">
            {/* Sidebar nav */}
            <nav className="w-64 border-r border-gray-800 bg-gray-900/30 p-4 hidden md:block sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-3">Documentation</p>
                <div className="space-y-0.5">
                    {DOCS_NAV.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className="flex items-center gap-3 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-md transition-colors"
                        >
                            <item.icon className="w-4 h-4 flex-shrink-0" />
                            {item.name}
                        </Link>
                    ))}
                </div>
            </nav>

            {/* Main content */}
            <main className="flex-1 overflow-auto p-8">
                <div className="max-w-3xl prose prose-invert prose-headings:text-white prose-p:text-gray-300 prose-a:text-indigo-400 prose-a:hover:text-indigo-300 prose-code:text-indigo-300 prose-code:bg-gray-800/50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-800 prose-strong:text-white prose-li:text-gray-300">
                    {children}
                </div>
            </main>
        </div>
    );
}
