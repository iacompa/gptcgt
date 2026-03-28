import { NextRequest } from 'next/server';
import { getSession } from '@/lib/auth';
import { CHAT_COMPLETIONS_URL } from '@/lib/config';

export const dynamic = 'force-dynamic';

/**
 * POST /api/chat
 * 
 * Proxies chat requests to the gptcgt proxy/v1/chat/completions endpoint
 * with the user's session cookie for auth. Streams SSE responses back.
 */
export async function POST(request: NextRequest) {
    const session = await getSession();
    if (!session) {
        return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const messages = body.messages || [];

    // Get session cookie to forward as auth
    const sessionCookie = request.cookies.get('gptcgt_session')?.value;
    if (!sessionCookie) {
        return Response.json({ error: 'Session expired' }, { status: 401 });
    }

    try {
        const proxyRes = await fetch(CHAT_COMPLETIONS_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionCookie}`,
            },
            body: JSON.stringify({
                messages,
                model: body.model || "gpt-4o-mini",
                stream: true,
            }),
        });

        if (!proxyRes.ok) {
            const err = await proxyRes.json().catch(() => ({}));
            return Response.json(
                { error: err.detail || err.error || 'Proxy request failed' },
                { status: proxyRes.status }
            );
        }

        if (!proxyRes.body) {
            return Response.json({ error: 'Proxy response body missing' }, { status: 502 });
        }

        return new Response(proxyRes.body, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        });
    } catch (err: any) {
        console.error('Chat proxy error:', err?.message);
        return Response.json(
            { error: 'Failed to connect to proxy' },
            { status: 502 }
        );
    }
}
