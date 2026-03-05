import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { jwtVerify } from 'jose';

export async function middleware(request: NextRequest) {
    const sessionCookie = request.cookies.get('gptcgt_session');

    // Protect all /dashboard routes
    if (request.nextUrl.pathname.startsWith('/dashboard')) {
        let isValid = false;

        if (sessionCookie?.value) {
            try {
                const secret = new TextEncoder().encode(process.env.JWT_SECRET || '');
                if (secret.length >= 32) {
                    await jwtVerify(sessionCookie.value, secret, {
                        algorithms: ['HS256'],
                        issuer: 'gptcgt',
                        audience: 'gptcgt-api'
                    });
                    isValid = true;
                }
            } catch (e) {
                console.error('Middleware JWT verification failed');
            }
        }

        if (!isValid) {
            // Redirect unauthenticated users to the auth page
            const url = request.nextUrl.clone();
            url.pathname = '/auth';
            url.searchParams.set('redirect_url', request.nextUrl.pathname);
            const response = NextResponse.redirect(url);
            response.cookies.delete('gptcgt_session');
            return response;
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: ['/dashboard/:path*'],
};
