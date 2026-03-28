import { NextResponse } from 'next/server';
import { createSessionToken } from '@/lib/auth';
import { API_URL, AUTH_CALLBACK_ORIGIN, BASE_URL, IS_PRODUCTION } from '@/lib/config';

export const dynamic = 'force-dynamic';

/**
 * POST handler for email/password signin.
 * 
 * Sends credentials to the FastAPI backend `/auth/signin` endpoint
 * which validates against WorkOS or local auth and returns user info.
 */
export async function POST(request: Request) {
    try {
        const body = await request.json();
        const email = String(body?.email || "").trim().toLowerCase();
        const password = String(body?.password || "");

        if (!email) {
            return NextResponse.json({ error: 'Email is required' }, { status: 400 });
        }

        if (password.length < 8) {
            return NextResponse.json(
                { error: 'Password must be at least 8 characters' },
                { status: 400 }
            );
        }

        // Validate against backend auth endpoint
        const backendRes = await fetch(`${API_URL}/auth/signin`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        if (!backendRes.ok) {
            const backendError = await backendRes.json().catch(() => ({}));
            return NextResponse.json(
                { error: backendError.detail || 'Invalid email or password' },
                { status: 401 }
            );
        }

        const backendData = await backendRes.json();
        const userId = backendData.workos_user_id || backendData.user_id || backendData.sub;

        if (!userId) {
            return NextResponse.json(
                { error: 'Authentication failed: no user ID returned' },
                { status: 500 }
            );
        }

        // Issue session token with verified identity
        const token = createSessionToken(
            String(userId),
            email,
            backendData.name || email.split('@')[0]
        );

        const response = NextResponse.json({
            success: true,
            email,
        });

        // httpOnly cookie only — no token in response body
        response.cookies.set('gptcgt_session', token, {
            httpOnly: true,
            secure: IS_PRODUCTION,
            sameSite: 'strict',
            path: '/',
            maxAge: 60 * 60 * 24, // 24 hours
        });

        return response;
    } catch (error: any) {
        console.error('Sign-in error:', error?.message);
        return NextResponse.json(
            { error: 'Sign in failed. Please try again.' },
            { status: 500 }
        );
    }
}

// WorkOS SSO redirect — one-click Google/GitHub login
export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const provider = searchParams.get('provider') || 'google';

    const workosClientId = process.env.WORKOS_CLIENT_ID;
    const redirectUri = `${AUTH_CALLBACK_ORIGIN}/api/auth/callback`;

    if (!workosClientId) {
        // Fallback: redirect to email/password auth page
        return NextResponse.redirect(
            new URL('/auth', BASE_URL)
        );
    }

    const providerMap: Record<string, string> = {
        authkit: 'authkit',
        github: 'GitHubOAuth',
        google: 'GoogleOAuth',
        microsoft: 'MicrosoftOAuth',
        apple: 'AppleOAuth',
        salesforce: 'SalesforceOAuth',
    };
    const workosProvider = providerMap[provider.toLowerCase()] || 'authkit';

    // Redirect to WorkOS User Management authorization
    const authUrl = new URL('https://api.workos.com/user_management/authorize');
    authUrl.searchParams.set('client_id', workosClientId);
    authUrl.searchParams.set('redirect_uri', redirectUri);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('provider', workosProvider);

    // P1-01: CSRF state verification
    const state = crypto.randomUUID();
    authUrl.searchParams.set('state', state);

    const response = NextResponse.redirect(authUrl.toString());
    response.cookies.set('oauth_state', state, {
        httpOnly: true,
        secure: IS_PRODUCTION,
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 10, // 10 minutes
    });

    return response;
}
