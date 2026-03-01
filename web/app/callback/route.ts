import { handleAuth } from '@workos-inc/authkit-nextjs';
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Use onError callback to expose the actual error from WorkOS
export const GET = handleAuth({
    returnPathname: '/dashboard',
    onError: async ({ error }) => {
        const message = error instanceof Error ? error.message : String(error);
        const stack = error instanceof Error ? error.stack : undefined;
        console.error('[CALLBACK AUTH ERROR]', message);
        console.error('[CALLBACK AUTH STACK]', stack);
        return NextResponse.json(
            {
                error: 'Authentication callback failed',
                detail: message,
                stack: stack?.split('\n').slice(0, 5),
                hint: 'Verify WORKOS_CLIENT_ID and WORKOS_API_KEY match your WorkOS environment (staging vs production). Check that WORKOS_COOKIE_PASSWORD is at least 32 characters.',
            },
            { status: 500 }
        );
    },
});
