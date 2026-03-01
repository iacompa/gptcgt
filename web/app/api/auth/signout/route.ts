import { NextResponse } from "next/server";

export const dynamic = 'force-dynamic';

export async function GET() {
    const response = NextResponse.redirect(new URL("/", process.env.NEXT_PUBLIC_BASE_URL || "https://gptcgt.ai"));
    response.cookies.delete("gptcgt_session");
    return response;
}
