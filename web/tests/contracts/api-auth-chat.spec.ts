import { expect, test } from "@playwright/test";

const hasTarget = (process.env.CONTRACT_BASE_URL || process.env.NEXT_PUBLIC_BASE_URL || "").trim().length > 0;

test.describe("public API contract checks", () => {
    test.describe.configure({ mode: "parallel" });

    test.skip(!hasTarget, "Set CONTRACT_BASE_URL or NEXT_PUBLIC_BASE_URL to run contract checks.");

    test("POST /api/chat returns unauthorized without session cookie", async ({ request }) => {
        const response = await request.post("/api/chat", {
            data: {
                messages: [{ role: "user", content: "ping" }],
            },
        });

        expect(response.status()).toBe(401);
        const payload = await response.json();
        expect(payload).toHaveProperty("error", "Unauthorized");
    });

    test("GET /api/auth/signin redirects to app auth when WorkOS client ID is missing", async ({ request }) => {
        const response = await request.get("/api/auth/signin?provider=google", {
            maxRedirects: 0,
        });

        expect([302, 307]).toContain(response.status());
        const location = response.headers()["location"] || "";
        expect(location).toContain("/auth");
    });

    test("GET /api/auth/callback requires code and surfaces error via redirect", async ({ request }) => {
        const response = await request.get("/api/auth/callback", {
            maxRedirects: 0,
        });

        expect([302, 307]).toContain(response.status());
        const location = response.headers()["location"] || "";
        expect(location).toContain("/auth");
        expect(location).toContain("missing_code");
    });

    test("GET /api/auth/callback with error query propagates redirect error page parameter", async ({ request }) => {
        const response = await request.get("/api/auth/callback?error=access_denied", {
            maxRedirects: 0,
        });

        expect([302, 307]).toContain(response.status());
        const location = response.headers()["location"] || "";
        expect(location).toContain("/auth");
        expect(location).toContain("error=access_denied");
    });
});
