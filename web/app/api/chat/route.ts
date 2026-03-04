import { NextRequest } from 'next/server';
import { getSession } from '@/lib/auth';

export const dynamic = 'force-dynamic';

const API_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

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
        const proxyRes = await fetch(`${API_URL}/proxy/v1/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionCookie}`,
            },
            body: JSON.stringify({
                messages,
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

        // Stream the SSE response through to the client
        const stream = new ReadableStream({
            async start(controller) {
                const reader = proxyRes.body?.getReader();
                if (!reader) {
                    controller.close();
                    return;
                }

                try {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        controller.enqueue(value);
                    }
                } catch (err) {
                    console.error('Stream error:', err);
                } finally {
                    controller.close();
                }
            },
        });

        return new Response(stream, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
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
