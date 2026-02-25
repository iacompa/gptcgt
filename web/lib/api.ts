"use client";

// Simplistic client-side fetch wrapper. 
// In Next 14 App Router, it's generally better to fetch on the server or pass tokens down.
// Since AuthKit relies on a server-level iron-session, we rely on a `/api/proxy` to forward requests 
// or require the dashboard pages to fetch their own token/session using server components.

// For these client components, we will assume we hit a Next API route that forwards to FastAPI
// Or assuming the cookie is naturally carried (if on same domain).

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
    // If we had a Next API route proxy, we'd hit `/api/backend${endpoint}`. 
    // But we have CORS enabled on FastAPI. We can pass the cookie if on same domain,
    // but for local dev with separate ports we need to manually pass a token.
    // To keep it simple for this fix, we will just read from a cookie or local storage if available, 
    // or rely on server-components to pass the data as props.

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const url = `${baseUrl}${endpoint}`;

    const headers = new Headers(options.headers || {});
    headers.set("Content-Type", "application/json");

    // Automatically inject JWT if present in localStorage (Client)
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("gptcgt_access_token");
        if (token && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${token}`);
        }
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
