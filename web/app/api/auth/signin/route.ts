import { NextResponse } from 'next/server';
import { createSessionToken } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
    try {
        const body = await request.json();
        const { email, password } = body;

        if (!email) {
            return NextResponse.json({ error: 'Email is required' }, { status: 400 });
        }

        // For MVP: accept any email with a non-empty password
        // Later: validate against FastAPI backend
        if (!password || password.length < 6) {
            return NextResponse.json({ error: 'Password must be at least 6 characters' }, { status: 400 });
        }

        const token = createSessionToken(email);

        const response = NextResponse.json({ success: true, email });

        // Set HTTP-only cookie with the JWT
        response.cookies.set('gptcgt_session', token, {
            httpOnly: true,
            secure: true,
            sameSite: 'lax',
            path: '/',
            maxAge: 60 * 60 * 24 * 7, // 7 days
        });

        return response;
    } catch (error: any) {
        return NextResponse.json({ error: error?.message || 'Sign in failed' }, { status: 500 });
    }
}

// Keep GET for backward compatibility — redirect to auth page
export async function GET() {
    return NextResponse.redirect(new URL('/auth', process.env.NEXT_PUBLIC_BASE_URL || 'https://gptcgt.ai'));
}
