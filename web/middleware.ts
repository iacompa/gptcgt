import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { jwtVerify } from 'jose';
import { getRequestOrigin } from '@/lib/request';

export async function middleware(request: NextRequest) {
    const sessionCookie = request.cookies.get('gptcgt_session');
    const jwtIssuer = process.env.WORKOS_ISSUER || 'gptcgt';
    const jwtAudience = process.env.WORKOS_AUDIENCE || 'gptcgt-api';

    // Protect all /dashboard routes
    if (request.nextUrl.pathname.startsWith('/dashboard')) {
        let isValid = false;

        if (sessionCookie?.value) {
            try {
                const secret = new TextEncoder().encode(process.env.JWT_SECRET || '');
                if (secret.length >= 32) {
                    await jwtVerify(sessionCookie.value, secret, {
                        algorithms: ['HS256'],
                        issuer: jwtIssuer,
                        audience: jwtAudience,
                    });
                    isValid = true;
                }
            } catch (e) {
                console.error('Middleware JWT verification failed');
            }
        }

        if (!isValid) {
            // Redirect unauthenticated users to the auth page
            const redirectPath = `/auth?redirect_url=${encodeURIComponent(request.nextUrl.pathname)}`;
            const redirectOrigin = getRequestOrigin(request) || new URL(request.url).origin;
            return new Response(null, {
                status: 307,
                headers: {
                    Location: new URL(redirectPath, redirectOrigin).toString(),
                    "Set-Cookie": "gptcgt_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT",
                },
            });
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: ['/dashboard/:path*'],
};
