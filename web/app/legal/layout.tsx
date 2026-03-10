// Phase 6: Part C — Legal Documents Layout
// Created: Phase 6 Polish & Launch Prep
export default function LegalLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="page-shell py-12">
            <div className="panel-dark mx-auto max-w-4xl px-6 py-10 sm:px-10">
                <div className="prose prose-invert max-w-3xl prose-headings:text-white prose-p:text-slate-300 prose-li:text-slate-300">
                    {children}
                </div>
            </div>
        </div>
    );
}
