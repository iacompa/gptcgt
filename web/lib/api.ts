"use client";

// Client-side fetch wrapper for the FastAPI backend.
// Uses httpOnly cookie for authentication — no localStorage token storage.

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const url = `${baseUrl}${endpoint}`;

    const headers = new Headers(options.headers || {});
    headers.set("Content-Type", "application/json");

    // SECURITY: Authentication is handled via httpOnly cookie.
    // The cookie is automatically sent by the browser with credentials: "include".
    // No token is stored in localStorage (XSS-accessible).

    const response = await fetch(url, {
        ...options,
        headers,
        credentials: "include",  // Send httpOnly cookie automatically
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
