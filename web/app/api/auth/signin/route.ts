import { NextResponse } from "next/server";
import { cookies } from "next/headers";

// WorkOS AuthKit handles the actual sign-in via PKCE OAuth redirect.
// This route initiates the SSO redirect; it does NOT receive email/password.
// Token exchange happens automatically in /auth/callback/route.ts via handleAuth().
export async function GET(_request: Request) {
    // Delegate entirely to WorkOS AuthKit which sets an HTTP-only session cookie.
    // The form in auth/page.tsx should link to /api/auth/signin (GET), not POST.
    const { redirect } = await import("next/navigation");
    const signInUrl = process.env.WORKOS_SIGNIN_URL;
    if (signInUrl) {
        redirect(signInUrl);
    }
    // Fallback if env not configured
    return NextResponse.redirect(new URL("/auth?error=not_configured", _request.url));
}

// POST is kept for future email/magic-link flows but must NOT pass token in URL.
// Token storage uses HTTP-only cookies only (via WorkOS authkit session).
export async function POST(request: Request) {
    try {
        const formData = await request.formData();
        const email = formData.get("email") as string;

        if (!email) {
            return NextResponse.json({ error: "email required" }, { status: 400 });
        }

        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${baseUrl}/auth/magic-link`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
        });

        if (!res.ok) {
            return NextResponse.redirect(new URL("/auth?error=true", request.url));
        }

        // Success: redirect to a "check your email" page, never pass token in URL
        return NextResponse.redirect(new URL("/auth?sent=true", request.url));
    } catch (_e) {
        return NextResponse.redirect(new URL("/auth?error=true", request.url));
    }
}
