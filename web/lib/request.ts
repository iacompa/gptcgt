import { NextRequest } from "next/server";

export function getRequestOrigin(request: NextRequest): string {
    const headersHost = request.headers.get("x-forwarded-host");
    const headersProto = request.headers.get("x-forwarded-proto");

    const rawHost = headersHost?.split(",")[0]?.trim();
    const rawProto = headersProto?.split(",")[0]?.trim();

    if (rawHost && rawProto) {
        return `${rawProto}://${rawHost}`;
    }

    return request.nextUrl.origin;
}
