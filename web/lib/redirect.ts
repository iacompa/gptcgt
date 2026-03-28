import { NextRequest, NextResponse } from "next/server";
import { getRequestOrigin } from "@/lib/request";

export function sameOriginRedirect(request: NextRequest, path: string, status = 307): NextResponse {
    if (!path.startsWith("/")) {
        throw new Error(`sameOriginRedirect expected an absolute path, received: ${path}`);
    }

    const origin = getRequestOrigin(request) || new URL(request.url).origin;
    return NextResponse.redirect(new URL(path, origin), status);
}
