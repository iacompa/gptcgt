import { getSession } from "@/lib/auth";
import { API_URL } from "@/lib/config";
import createClient from "openapi-fetch";
import type { paths } from "./api-schema";

export async function getServerApiClient() {
    const session = await getSession();
    const token = session?.accessToken;

    return createClient<paths>({
        baseUrl: API_URL,
        headers: token ? {
            "Authorization": `Bearer ${token}`
        } : {}
    });
}

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
    const session = await getSession();
    const token = session?.accessToken;

    const url = `${API_URL}${endpoint}`;

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
