import { handleAuth } from '@workos-inc/authkit-nextjs';
import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Wrap handleAuth to catch and log errors
const authHandler = handleAuth({ returnPathname: '/dashboard' });

export const GET = async (request: NextRequest) => {
    try {
        return await authHandler(request);
    } catch (error: any) {
        console.error('[CALLBACK ERROR]', error?.message || error);
        console.error('[CALLBACK STACK]', error?.stack);
        // Return a user-friendly error instead of a 500
        return NextResponse.json(
            {
                error: 'Authentication failed',
                detail: error?.message || 'Unknown error during callback',
                hint: 'Check that WORKOS_CLIENT_ID, WORKOS_API_KEY, WORKOS_COOKIE_PASSWORD, and NEXT_PUBLIC_WORKOS_REDIRECT_URI are correctly configured in Vercel environment variables.'
            },
            { status: 500 }
        );
    }
};
