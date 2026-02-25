import { NextResponse } from "next/server";

export async function GET() {
    // Clear session cookie and redirect to home
    const response = NextResponse.redirect(new URL("/", process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000"));
    response.cookies.delete("session");
    return response;
}
