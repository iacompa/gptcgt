import createClient from "openapi-fetch";
import type { paths } from "./api-schema";

function credentialedFetch(input: RequestInfo | URL, init?: RequestInit) {
    if (input instanceof Request) {
        const method = init?.method ?? input.method;
        const headers = new Headers(input.headers);

        if (init?.headers) {
            new Headers(init.headers).forEach((value, key) => {
                headers.set(key, value);
            });
        }

        return fetch(input.url, {
            ...init,
            method,
            headers,
            body:
                method === "GET" || method === "HEAD"
                    ? undefined
                    : (init?.body ?? input.body),
            credentials: "include",
        });
    }

    return fetch(input, {
        ...init,
        credentials: "include",
    });
}

export const apiClient = createClient<paths>({
    baseUrl: "/api/backend",
    // openapi-fetch may pass either a Request or a URL+init pair.
    // Rebuild the outgoing request so same-origin dashboard calls always
    // carry the httpOnly session cookie into the Next proxy route.
    fetch: credentialedFetch,
});
