import { NextResponse } from "next/server";
import { BASE_URL } from "@/lib/config";

export const dynamic = 'force-dynamic';

// F16: Sign-out MUST be POST (state-changing action), not GET.
export async function POST() {
    const response = NextResponse.json({ success: true });
    response.cookies.delete("gptcgt_session");
    return response;
}


