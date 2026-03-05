import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { API_URL } from "@/lib/config";

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
    const session = await getSession();
    if (!session) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const start_date = searchParams.get("start_date") || "";
    const end_date = searchParams.get("end_date") || "";

    let url = `${API_URL}/usage/?`;
    if (start_date) url += `start_date=${start_date}&`;
    if (end_date) url += `end_date=${end_date}&`;

    const res = await fetch(url, {
        headers: {
            Authorization: `Bearer ${session.accessToken}`,
        },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}
