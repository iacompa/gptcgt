import { cookies } from "next/headers";
import { API_URL } from "@/lib/config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP_HEADERS = new Set([
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
]);

function buildUpstreamUrl(path: string[], search: string): string {
    const baseUrl = API_URL.replace(/\/$/, "");
    const normalizedPath = path.join("/");
    return `${baseUrl}/${normalizedPath}${search}`;
}

function buildUpstreamHeaders(
    request: Request,
    auth: { sessionToken?: string; cookieHeader?: string | null }
): Headers {
    const headers = new Headers();

    request.headers.forEach((value, key) => {
        const lower = key.toLowerCase();
        if (
            !HOP_BY_HOP_HEADERS.has(lower) &&
            lower !== "cookie" &&
            lower !== "authorization"
        ) {
            headers.set(key, value);
        }
    });

    if (auth.sessionToken) {
        headers.set("authorization", `Bearer ${auth.sessionToken}`);
    }

    if (auth.cookieHeader) {
        headers.set("cookie", auth.cookieHeader);
    }

    return headers;
}

function buildResponseHeaders(upstream: Headers): Headers {
    const headers = new Headers();

    upstream.forEach((value, key) => {
        if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
            headers.set(key, value);
        }
    });

    return headers;
}

async function proxyRequest(
    request: Request,
    { params }: { params: Promise<{ path: string[] }> }
): Promise<Response> {
    const [{ path }, cookieStore] = await Promise.all([params, cookies()]);
    const requestUrl = new URL(request.url);
    const upstreamUrl = buildUpstreamUrl(path, requestUrl.search);
    const method = request.method.toUpperCase();
    const rawCookieHeader = request.headers.get("cookie");
    const serializedCookies =
        cookieStore
            .getAll()
            .map(({ name, value }) => `${name}=${value}`)
            .join("; ") || null;
    const rawSessionCookie = rawCookieHeader
        ?.split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith("gptcgt_session="));
    const sessionToken =
        cookieStore.get("gptcgt_session")?.value ||
        (rawSessionCookie ? rawSessionCookie.slice("gptcgt_session=".length) : undefined);

    const body =
        method === "GET" || method === "HEAD"
            ? undefined
            : await request.arrayBuffer();

    const upstream = await fetch(upstreamUrl, {
        method,
        headers: buildUpstreamHeaders(request, {
            sessionToken,
            cookieHeader: rawCookieHeader || serializedCookies,
        }),
        body,
        redirect: "manual",
        cache: "no-store",
    });

    return new Response(upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers: buildResponseHeaders(upstream.headers),
    });
}

export async function GET(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}

export async function POST(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}

export async function PUT(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}

export async function PATCH(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}

export async function DELETE(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}

export async function HEAD(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}

export async function OPTIONS(
    request: Request,
    context: { params: Promise<{ path: string[] }> }
) {
    return proxyRequest(request, context);
}
