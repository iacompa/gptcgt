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
        <div className="flex h-full">
            {/* Sidebar Component */}
            <DashboardNav session={session} />

            {/* Main content */}
            <div className="flex-1 overflow-auto bg-gray-950 p-8">
                <div className="max-w-5xl mx-auto">
                    {children}
                </div>
            </div>
        </div>
    );
}
