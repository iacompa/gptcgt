import { getSession } from "@/lib/auth";

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
    const session = await getSession();
    const token = session?.accessToken;

    const baseUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const url = `${baseUrl}${endpoint}`;

    const headers = new Headers(options.headers || {});
    headers.set("Content-Type", "application/json");

    if (token) {
        // We send the token. The proxy verifies this. In development we might bypass using the ID mapping directly if complex OIDC is missing
        headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    if (!response.ok) {
        let errorDetail = "API Error";
        try {
            const errorJson = await response.json();
            errorDetail = errorJson.detail || errorJson.error || errorDetail;
        } catch { }
        throw new Error(errorDetail);
    }

    return response.json();
}
