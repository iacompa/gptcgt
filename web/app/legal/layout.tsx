// Phase 6: Part C — Legal Documents Layout
// Created: Phase 6 Polish & Launch Prep
export default function LegalLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="min-h-screen bg-gray-950 py-16 px-4">
            <div className="max-w-3xl mx-auto prose prose-invert prose-headings:text-white prose-p:text-gray-300">
                {children}
            </div>
        </div>
    );
}
