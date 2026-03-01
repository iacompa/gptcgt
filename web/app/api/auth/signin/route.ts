import { getSignInUrl } from '@workos-inc/authkit-nextjs';
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export const GET = async (request: Request) => {
    try {
        const signInUrl = await getSignInUrl();
        console.log('[SIGNIN] Redirecting to:', signInUrl);
        return NextResponse.redirect(signInUrl);
    } catch (error: any) {
        console.error('[SIGNIN ERROR]', error?.message || error);
        console.error('[SIGNIN STACK]', error?.stack);
        // Return the error as JSON so we can debug
        return NextResponse.json(
            {
                error: 'Failed to generate sign-in URL',
                detail: error?.message || String(error),
                stack: error?.stack?.split('\n').slice(0, 5),
                envCheck: {
                    hasClientId: !!process.env.WORKOS_CLIENT_ID,
                    hasApiKey: !!process.env.WORKOS_API_KEY,
                    hasCookiePassword: !!process.env.WORKOS_COOKIE_PASSWORD,
                    hasRedirectUri: !!process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI,
                    redirectUri: process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI,
                },
            },
            { status: 500 }
        );
    }
};
