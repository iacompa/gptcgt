import { NextResponse, NextRequest } from 'next/server';
import { createSessionToken } from '@/lib/auth';
import { API_URL, BASE_URL, IS_PRODUCTION } from '@/lib/config';

export const dynamic = 'force-dynamic';

/**
 * WorkOS SSO callback handler.
 * 
 * After the user authenticates with Google/GitHub via WorkOS,
 * WorkOS redirects back here with an authorization code.
 * We exchange it for a user profile and create a session.
 */
export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const code = searchParams.get('code');
    const error = searchParams.get('error');


    const state = searchParams.get('state');

    if (error) {
        return NextResponse.redirect(`${BASE_URL}/auth?error=${encodeURIComponent(error)}`);
    }

    if (!code) {
        return NextResponse.redirect(`${BASE_URL}/auth?error=missing_code`);
    }

    // P1-01: Validate OAuth state to prevent CSRF
    const storedState = request.cookies.get('oauth_state')?.value;
    if (!state || !storedState || state !== storedState) {
        console.error('SSO callback CSRF state mismatch:', { state, storedState });
        return NextResponse.redirect(`${BASE_URL}/auth?error=invalid_state`);
    }

    try {
        // Exchange the auth code via our backend
        const backendRes = await fetch(`${API_URL}/auth/sso/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        });

        if (!backendRes.ok) {
            const err = await backendRes.json().catch(() => ({}));
            console.error('SSO callback backend error:', err);
            return NextResponse.redirect(`${BASE_URL}/auth?error=sso_failed`);
        }

        const data = await backendRes.json();
        const email = data.email || data.profile?.email;
        const name = data.name || data.profile?.name || email?.split('@')[0];

        if (!email) {
            return NextResponse.redirect(`${BASE_URL}/auth?error=no_email`);
        }

        // Create session token (subject should be stable user id when available)
        const subject = data.workos_user_id || data.user_id || email;
        const token = createSessionToken(subject, email, name);

        // Redirect to dashboard with httpOnly session cookie
        const response = NextResponse.redirect(`${BASE_URL}/dashboard`);
        response.cookies.delete('oauth_state'); // Clear CSRF state
        response.cookies.set('gptcgt_session', token, {
            httpOnly: true,
            secure: IS_PRODUCTION,
            sameSite: 'lax',
            path: '/',
            maxAge: 60 * 60 * 24 * 7,
        });

        return response;
    } catch (err: any) {
        console.error('SSO callback error:', err?.message);
        return NextResponse.redirect(`${BASE_URL}/auth?error=callback_failed`);
    }
}
