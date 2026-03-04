import { NextResponse } from "next/server";

export const dynamic = 'force-dynamic';

// F16: Sign-out MUST be POST (state-changing action), not GET.
export async function POST() {
    const response = NextResponse.json({ success: true });
    response.cookies.delete("gptcgt_session");
    return response;
}

// Backwards-compatible GET redirect (e.g. old bookmarks or nav links)
export async function GET() {
    const response = NextResponse.redirect(new URL("/", process.env.NEXT_PUBLIC_BASE_URL || "https://gptcgt.ai"));
    response.cookies.delete("gptcgt_session");
    return response;
}
