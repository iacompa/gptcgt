import Link from 'next/link';
import { Book, Cpu, Keyboard, Key, Sliders, DollarSign, Database, HelpCircle } from 'lucide-react';

const DOCS_NAV = [
    { name: 'Overview', href: '/docs', icon: Book },
    { name: 'Operation Modes', href: '/docs/modes', icon: Cpu },
    { name: 'Commands & Shortcuts', href: '/docs/commands', icon: Keyboard },
    { name: 'API Keys & Auth', href: '/docs/keys', icon: Key },
    { name: 'Configuration', href: '/docs/config', icon: Sliders },
    { name: 'Costs & Billing', href: '/docs/costs', icon: DollarSign },
    { name: 'Custom Models', href: '/docs/custom-models', icon: Database },
    { name: 'FAQ', href: '/docs/faq', icon: HelpCircle },
];

export default function DocsLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-[calc(100vh-4rem)] bg-gray-950">
            {/* Sidebar nav */}
            <nav className="w-64 border-r border-gray-800 bg-gray-900/30 p-4 hidden md:block">
                <div className="space-y-1">
                    {DOCS_NAV.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className="flex items-center gap-3 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-md transition-colors"
                        >
                            <item.icon className="w-4 h-4" />
                            {item.name}
                        </Link>
                    ))}
                </div>
            </nav>

            {/* Main content */}
            <main className="flex-1 overflow-auto p-8">
                <div className="max-w-3xl prose prose-invert prose-headings:text-white prose-p:text-gray-300 prose-a:text-indigo-400 prose-a:hover:text-indigo-300">
                    {children}
                </div>
            </main>
        </div>
    );
}
