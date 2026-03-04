import { NextResponse } from 'next/server';
import { createSessionToken } from '@/lib/auth';

export const dynamic = 'force-dynamic';

const API_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

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
            secure: process.env.NODE_ENV === 'production',
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
    const redirectUri = `${process.env.NEXT_PUBLIC_BASE_URL || 'https://gptcgt.ai'}/api/auth/callback`;

    if (!workosClientId) {
        // Fallback: redirect to email/password auth page
        return NextResponse.redirect(
            new URL('/auth', process.env.NEXT_PUBLIC_BASE_URL || 'https://gptcgt.ai')
        );
    }

    // Redirect to WorkOS SSO authorization
    const authUrl = new URL('https://api.workos.com/sso/authorize');
    authUrl.searchParams.set('client_id', workosClientId);
    authUrl.searchParams.set('redirect_uri', redirectUri);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('provider', provider === 'github' ? 'authkit' : 'GoogleOAuth');

    return NextResponse.redirect(authUrl.toString());
}
