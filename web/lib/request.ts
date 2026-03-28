import { NextRequest } from "next/server";

function parseOrigin(candidate: string | null): string {
    if (!candidate) {
        return "";
    }

    try {
        return new URL(candidate).origin;
    } catch {
        return "";
    }
}

function isLoopbackOrigin(candidate: string): boolean {
    if (!candidate) {
        return false;
    }

    try {
        const { hostname } = new URL(candidate);
        return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1" || hostname === "[::1]";
    } catch {
        return false;
    }
}

export function getRequestOrigin(request: NextRequest): string {
    const headersHost = request.headers.get("x-forwarded-host");
    const headersProto = request.headers.get("x-forwarded-proto");
    const directHost = request.headers.get("host");

    const rawHost = headersHost?.split(",")[0]?.trim() || directHost?.split(",")[0]?.trim();
    const rawProto =
        headersProto?.split(",")[0]?.trim() ||
        request.nextUrl.protocol.replace(/:$/, "") ||
        new URL(request.url).protocol.replace(/:$/, "");
    const browserOrigin = parseOrigin(request.headers.get("origin")) || parseOrigin(request.headers.get("referer"));
    const hostOrigin = rawHost && rawProto ? `${rawProto}://${rawHost}` : "";

    if (browserOrigin && hostOrigin && browserOrigin !== hostOrigin) {
        if (isLoopbackOrigin(browserOrigin) && isLoopbackOrigin(hostOrigin)) {
            return browserOrigin;
        }
    }

    if (hostOrigin) {
        return hostOrigin;
    }

    return request.nextUrl.origin;
}
