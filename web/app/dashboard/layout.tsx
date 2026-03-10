import { DashboardNav } from "@/components/nav";
import { getSession } from "@/lib/auth";
import { redirect } from "next/navigation";

export const dynamic = 'force-dynamic';

export default async function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const session = await getSession();

    if (!session) {
        redirect("/auth");
    }

    return (
        <div className="page-shell">
            <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
                <aside className="xl:sticky xl:top-24 xl:h-fit">
                    <DashboardNav session={session} />
                </aside>
                <div className="panel min-w-0 overflow-hidden p-5 sm:p-8">
                    {children}
                </div>
            </div>
        </div>
    );
}
