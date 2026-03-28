import type { BrowserContext } from "@playwright/test";

function resolveSessionCookie(): string {
    const value =
        process.env.STAGING_WEB_SESSION_COOKIE ||
        "";
    return value.trim();
}

export function stagingWebBaseURL(): string {
    return (process.env.STAGING_WEB_BASE_URL || "").trim();
}

export function expectGithubConnected(): boolean {
    return (process.env.STAGING_WEB_EXPECT_GITHUB_CONNECTED || "false").trim().toLowerCase() === "true";
}

export async function installStagingSession(context: BrowserContext, baseURL: string) {
    const cookieValue = resolveSessionCookie();
    if (!cookieValue) {
        throw new Error(
            "Missing STAGING_WEB_SESSION_COOKIE or STAGING_SMOKE_AUTH_TOKEN for staging browser authentication."
        );
    }

    await context.addCookies([
        {
            name: "gptcgt_session",
            value: cookieValue,
            url: baseURL,
            httpOnly: true,
            sameSite: "Strict",
        },
    ]);
}
